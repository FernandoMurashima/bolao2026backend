from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from copa.models import Tournament, Stage, Match


class Command(BaseCommand):
    help = "Gera automaticamente os jogos das fases eliminatórias a partir dos resultados da fase de grupos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tournament-id",
            type=int,
            default=None,
            help="ID do Tournament. Se omitido e houver só um torneio, usa esse.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        tournament = self._get_tournament(options.get("tournament_id"))

        group_stage = self._get_stage(tournament, order=1)
        round32_stage = self._get_stage(tournament, order=2)
        quarter_stage = self._get_stage(tournament, order=3)
        semi_stage = self._get_stage(tournament, order=4)
        final_stage = self._get_stage(tournament, order=5)

        # 1) Gera Round-of-32 (oitavas do bolão) a partir da fase de grupos
        if not Match.objects.filter(tournament=tournament, stage=round32_stage).exists():
            self.stdout.write("Gerando Round-of-32 a partir da fase de grupos...")
            self._assert_all_decided(tournament, group_stage)
            self._generate_round32_from_groups(
                tournament, group_stage, round32_stage
            )
            self.stdout.write(self.style.SUCCESS("Round-of-32 gerado."))

        # 2) Gera quartas a partir do Round-of-32
        if (
            Match.objects.filter(tournament=tournament, stage=round32_stage).exists()
            and not Match.objects.filter(
                tournament=tournament, stage=quarter_stage
            ).exists()
        ):
            self.stdout.write("Gerando quartas de final a partir do Round-of-32...")
            self._assert_all_decided(tournament, round32_stage)
            self._generate_next_knockout_stage(
                tournament, round32_stage, quarter_stage
            )
            self.stdout.write(self.style.SUCCESS("Quartas geradas."))

        # 3) Gera semifinais a partir das quartas
        if (
            Match.objects.filter(tournament=tournament, stage=quarter_stage).exists()
            and not Match.objects.filter(tournament=tournament, stage=semi_stage).exists()
        ):
            self.stdout.write("Gerando semifinais a partir das quartas...")
            self._assert_all_decided(tournament, quarter_stage)
            self._generate_next_knockout_stage(
                tournament, quarter_stage, semi_stage
            )
            self.stdout.write(self.style.SUCCESS("Semifinais geradas."))

        # 4) Gera final + disputa de 3º a partir das semifinais
        if (
            Match.objects.filter(tournament=tournament, stage=semi_stage).exists()
            and not Match.objects.filter(tournament=tournament, stage=final_stage).exists()
        ):
            self.stdout.write("Gerando final e disputa de 3º lugar...")
            self._assert_all_decided(tournament, semi_stage)
            self._generate_final_and_third(
                tournament, semi_stage, final_stage
            )
            self.stdout.write(
                self.style.SUCCESS("Final e jogo de 3º lugar gerados.")
            )

    def _get_tournament(self, tournament_id):
        qs = Tournament.objects.all()
        if tournament_id is None:
            if qs.count() != 1:
                raise CommandError(
                    f"Existe(m) {qs.count()} torneio(s). Informe --tournament-id."
                )
            return qs.first()
        try:
            return qs.get(pk=tournament_id)
        except Tournament.DoesNotExist:
            raise CommandError(f"Tournament {tournament_id} não existe.")

    def _get_stage(self, tournament, order: int) -> Stage:
        try:
            return Stage.objects.get(tournament=tournament, order=order)
        except Stage.DoesNotExist:
            raise CommandError(
                f"Stage com order={order} não encontrado para o torneio {tournament.id}."
            )

    def _assert_all_decided(self, tournament, stage: Stage):
        missing = Match.objects.filter(
            tournament=tournament, stage=stage
        ).filter(
            home_score__isnull=True
        ) | Match.objects.filter(
            tournament=tournament, stage=stage, away_score__isnull=True
        )
        if missing.exists():
            raise CommandError(
                f"Ainda existem jogos sem placar oficial na fase '{stage.name}'."
            )

    # ---------- FASE DE GRUPOS -> ROUND-OF-32 ----------

    def _generate_round32_from_groups(self, tournament, group_stage, round32_stage):
        from collections import defaultdict

        group_matches = Match.objects.filter(
            tournament=tournament, stage=group_stage
        ).select_related("home_team", "away_team")

        # agrupa stats por grupo e time
        groups = defaultdict(dict)
        for m in group_matches:
            if not m.group_name:
                raise CommandError("Há jogo de fase de grupos sem group_name.")
            g = m.group_name

            for side in ("home", "away"):
                team = getattr(m, f"{side}_team")
                if team is None:
                    raise CommandError("Jogo de grupo sem time definido.")
                if team.id not in groups[g]:
                    groups[g][team.id] = {
                        "team": team,
                        "points": 0,
                        "gf": 0,
                        "ga": 0,
                    }

            hs = m.home_score
            as_ = m.away_score
            if hs is None or as_ is None:
                raise CommandError(
                    "Jogo de grupo sem placar em _generate_round32_from_groups."
                )

            # gols
            groups[g][m.home_team_id]["gf"] += hs
            groups[g][m.home_team_id]["ga"] += as_
            groups[g][m.away_team_id]["gf"] += as_
            groups[g][m.away_team_id]["ga"] += hs

            # pontos
            if hs > as_:
                groups[g][m.home_team_id]["points"] += 3
            elif as_ > hs:
                groups[g][m.away_team_id]["points"] += 3
            else:
                groups[g][m.home_team_id]["points"] += 1
                groups[g][m.away_team_id]["points"] += 1

        def sort_key(item):
            data = item[1]
            gd = data["gf"] - data["ga"]
            return (-data["points"], -gd, -data["gf"], data["team"].name)

        # ordena grupos e extrai 1º, 2º e 3º
        group_order = sorted(groups.keys())
        winners = {}
        runners = {}
        thirds = []

        for g in group_order:
            stats = groups[g]
            ranking = sorted(stats.items(), key=sort_key)
            if len(ranking) < 3:
                raise CommandError(f"Grupo {g} tem menos de 3 times.")

            first = ranking[0][1]
            second = ranking[1][1]
            third = ranking[2][1]

            winners[g] = first
            runners[g] = second
            thirds.append((g, third))

        # escolhe os 8 melhores 3os colocados
        thirds_sorted = sorted(
            thirds,
            key=lambda it: (
                -it[1]["points"],
                -(it[1]["gf"] - it[1]["ga"]),
                -it[1]["gf"],
                it[1]["team"].name,
            ),
        )
        best_thirds = thirds_sorted[:8]

        # monta pareamentos:
        # - 12 jogos entre 1º de um grupo x 2º de outro (pares A-B, C-D, E-F, G-H, I-J, K-L)
        # - 4 jogos entre os 8 melhores 3os (1x8, 2x7, 3x6, 4x5)
        pairings = []

        # pares fixos por grupo
        pairs = [("A", "B"), ("C", "D"), ("E", "F"), ("G", "H"), ("I", "J"), ("K", "L")]
        for g1, g2 in pairs:
            if g1 not in winners or g2 not in winners:
                continue
            pairings.append(
                (
                    winners[g1]["team"],
                    runners[g2]["team"],
                )
            )
            pairings.append(
                (
                    winners[g2]["team"],
                    runners[g1]["team"],
                )
            )

        # 4 jogos extras com os melhores 3os
        if len(best_thirds) < 8:
            raise CommandError(
                f"Esperados 8 melhores 3ºs colocados, encontrados {len(best_thirds)}."
            )

        idx_pairs = [(0, 7), (1, 6), (2, 5), (3, 4)]
        for i, j in idx_pairs:
            t1 = best_thirds[i][1]["team"]
            t2 = best_thirds[j][1]["team"]
            pairings.append((t1, t2))

        # cria jogos
        base_dt = round32_stage.deadline or group_stage.deadline or timezone.now()
        existing = Match.objects.filter(tournament=tournament, stage=round32_stage)
        if existing.exists():
            raise CommandError(
                "Já existem jogos cadastrados para o Round-of-32 deste torneio."
            )

        for idx, (home, away) in enumerate(pairings):
            kickoff = base_dt + timedelta(hours=idx)
            Match.objects.create(
                tournament=tournament,
                stage=round32_stage,
                home_team=home,
                away_team=away,
                kickoff=kickoff,
                group_name=None,
            )

    # ---------- FASE ELIMINATÓRIA GENÉRICA ----------

    def _generate_next_knockout_stage(self, tournament, from_stage, to_stage):
        prev_matches = list(
            Match.objects.filter(tournament=tournament, stage=from_stage).order_by(
                "kickoff", "id"
            )
        )
        if len(prev_matches) % 2 != 0:
            raise CommandError(
                f"Número de jogos na fase '{from_stage.name}' não é par."
            )

        base_dt = to_stage.deadline or from_stage.deadline or timezone.now()

        existing = Match.objects.filter(tournament=tournament, stage=to_stage)
        if existing.exists():
            raise CommandError(
                f"Já existem jogos cadastrados para a fase '{to_stage.name}'."
            )

        new_idx = 0
        for i in range(0, len(prev_matches), 2):
            m1 = prev_matches[i]
            m2 = prev_matches[i + 1]

            w1 = self._winner_from_match(m1)
            w2 = self._winner_from_match(m2)

            kickoff = base_dt + timedelta(hours=new_idx)
            Match.objects.create(
                tournament=tournament,
                stage=to_stage,
                home_team=w1,
                away_team=w2,
                kickoff=kickoff,
                group_name=None,
            )
            new_idx += 1

    def _generate_final_and_third(self, tournament, semi_stage, final_stage):
        semis = list(
            Match.objects.filter(tournament=tournament, stage=semi_stage).order_by(
                "kickoff", "id"
            )
        )
        if len(semis) != 2:
            raise CommandError(
                f"Esperado exatamente 2 jogos na fase '{semi_stage.name}'."
            )

        existing = Match.objects.filter(tournament=tournament, stage=final_stage)
        if existing.exists():
            raise CommandError(
                f"Já existem jogos cadastrados para a fase '{final_stage.name}'."
            )

        base_dt = final_stage.deadline or semi_stage.deadline or timezone.now()

        # vencedores -> final
        w1 = self._winner_from_match(semis[0])
        w2 = self._winner_from_match(semis[1])

        # perdedores -> 3º lugar
        l1 = self._loser_from_match(semis[0])
        l2 = self._loser_from_match(semis[1])

        # jogo de 3º lugar
        Match.objects.create(
            tournament=tournament,
            stage=final_stage,
            home_team=l1,
            away_team=l2,
            kickoff=base_dt,
            group_name="3º lugar",
        )

        # final
        Match.objects.create(
            tournament=tournament,
            stage=final_stage,
            home_team=w1,
            away_team=w2,
            kickoff=base_dt + timedelta(hours=3),
            group_name="Final",
        )

    def _winner_from_match(self, match: Match):
        if match.home_score is None or match.away_score is None:
            raise CommandError(
                f"Jogo id={match.id} sem placar para determinar vencedor."
            )
        if match.home_score == match.away_score:
            raise CommandError(
                f"Jogo id={match.id} terminou empatado. Defina um critério (pênaltis) antes de gerar a fase seguinte."
            )
        return match.home_team if match.home_score > match.away_score else match.away_team

    def _loser_from_match(self, match: Match):
        if match.home_score is None or match.away_score is None:
            raise CommandError(
                f"Jogo id={match.id} sem placar para determinar perdedor."
            )
        if match.home_score == match.away_score:
            raise CommandError(
                f"Jogo id={match.id} terminou empatado. Defina um critério (pênaltis) antes de gerar a fase seguinte."
            )
        return match.away_team if match.home_score > match.away_score else match.home_team
