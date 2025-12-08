from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from copa.models import Tournament, Stage, Team, Match


def aware(y, m, d, h, mi):
    """
    Cria datetime com timezone padrão do projeto (America/Sao_Paulo).
    Usado para start_date, extras_deadline, deadlines e kickoffs.
    """
    return timezone.make_aware(datetime(y, m, d, h, mi))


class Command(BaseCommand):
    help = "Seed da Copa do Mundo 2026: torneio, estágios, seleções e jogos da fase de grupos."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(">> Criando/atualizando Copa do Mundo 2026"))

        # 1) Tournament (sempre garante campos atualizados)
        start_date = aware(2026, 6, 11, 19, 0)       # jogo de abertura
        extras_deadline = aware(2026, 6, 10, 0, 0)   # prazo para extras

        tournament, created = Tournament.objects.get_or_create(
            name="Copa do Mundo 2026",
            defaults={
                "start_date": start_date,
                "extras_deadline": extras_deadline,
            },
        )

        if not created:
            # garante que os campos estão com os valores que queremos
            tournament.start_date = start_date
            tournament.extras_deadline = extras_deadline
            tournament.save(update_fields=["start_date", "extras_deadline"])
            self.stdout.write(self.style.WARNING("Tournament já existia, campos atualizados."))
        else:
            self.stdout.write(self.style.SUCCESS("Tournament criado."))

        # 2) Stages (fases) com pontuação e deadlines
        self.stdout.write(self.style.MIGRATE_HEADING(">> Criando/atualizando estágios (fases)"))

        # order, name, deadline, points_exact_score, points_result, points_one_team_goals
        stage_data = [
            (1, "Fase de grupos",      aware(2026, 6, 11, 0, 0),  25, 10, 5),
            (2, "Oitavas de final",    aware(2026, 6, 30, 0, 0),  50, 20, 10),
            (3, "Quartas de final",    aware(2026, 7, 6, 0, 0),   100, 40, 20),
            (4, "Semifinais",          aware(2026, 7, 12, 0, 0),  200, 80, 40),
            (5, "3º lugar + Final",    aware(2026, 7, 18, 0, 0),  400, 160, 80),
        ]

        stages = {}

        for order, name, deadline, pe, pr, pg in stage_data:
            stage, s_created = Stage.objects.get_or_create(
                tournament=tournament,
                order=order,
                defaults={
                    "name": name,
                    "deadline": deadline,
                    "points_exact_score": pe,
                    "points_result": pr,
                    "points_one_team_goals": pg,
                },
            )

            # Mesmo que já exista, vamos garantir que está com os valores corretos.
            changed = False
            if stage.name != name:
                stage.name = name
                changed = True
            if stage.deadline != deadline:
                stage.deadline = deadline
                changed = True
            if stage.points_exact_score != pe:
                stage.points_exact_score = pe
                changed = True
            if stage.points_result != pr:
                stage.points_result = pr
                changed = True
            if stage.points_one_team_goals != pg:
                stage.points_one_team_goals = pg
                changed = True

            if changed:
                stage.save()
                msg = "criado" if s_created else "atualizado"
                self.stdout.write(self.style.SUCCESS(f"Stage {order} ({name}) {msg}/sincronizado."))
            else:
                self.stdout.write(self.style.WARNING(f"Stage {order} ({name}) já estava sincronizado."))

            stages[order] = stage

        # 3) Times (48 participantes, incluindo vagas de playoff)
        self.stdout.write(self.style.MIGRATE_HEADING(">> Criando/atualizando seleções"))

        team_data = [
            # code, name
            ("MEX", "Mexico"),
            ("RSA", "South Africa"),
            ("KOR", "South Korea"),
            ("EPD", "European Playoff D"),

            ("CAN", "Canada"),
            ("EPA", "European Playoff A"),
            ("QAT", "Qatar"),
            ("SUI", "Switzerland"),

            ("BRA", "Brazil"),
            ("MAR", "Morocco"),
            ("HAI", "Haiti"),
            ("SCO", "Scotland"),

            ("USA", "United States"),
            ("PAR", "Paraguay"),
            ("AUS", "Australia"),
            ("EPC", "European Playoff C"),

            ("GER", "Germany"),
            ("CUW", "Curacao"),
            ("CIV", "Ivory Coast"),
            ("ECU", "Ecuador"),

            ("NED", "Netherlands"),
            ("JPN", "Japan"),
            ("EPB", "European Playoff B"),
            ("TUN", "Tunisia"),

            ("BEL", "Belgium"),
            ("EGY", "Egypt"),
            ("IRN", "IR Iran"),
            ("NZL", "New Zealand"),

            ("ESP", "Spain"),
            ("CPV", "Cape Verde"),
            ("KSA", "Saudi Arabia"),
            ("URU", "Uruguay"),

            ("FRA", "France"),
            ("SEN", "Senegal"),
            ("FP2", "FIFA Playoff 2"),
            ("NOR", "Norway"),

            ("ARG", "Argentina"),
            ("ALG", "Algeria"),
            ("AUT", "Austria"),
            ("JOR", "Jordan"),

            ("POR", "Portugal"),
            ("FP1", "FIFA Playoff 1"),
            ("UZB", "Uzbekistan"),
            ("COL", "Colombia"),

            ("ENG", "England"),
            ("CRO", "Croatia"),
            ("GHA", "Ghana"),
            ("PAN", "Panama"),
        ]

        teams = {}
        for code, name in team_data:
            team, t_created = Team.objects.get_or_create(
                code=code,
                defaults={"name": name},
            )
            if not t_created and team.name != name:
                team.name = name
                team.save(update_fields=["name"])
            teams[code] = team

        self.stdout.write(self.style.SUCCESS(f"{len(teams)} seleções criadas/atualizadas."))

        # 4) Jogos da fase de grupos (Stage 1)
        self.stdout.write(self.style.MIGRATE_HEADING(">> Criando/atualizando jogos da fase de grupos"))

        s1 = stages[1]

        # Dados da fase de grupos (grupo A–L)
        # Formato: (group, home_code, away_code, (year, month, day, hour, minute))
        group_matches = [
            # GROUP A
            ("A", "MEX", "RSA", (2026, 6, 11, 19, 0)),
            ("A", "KOR", "EPD", (2026, 6, 12, 2, 0)),
            ("A", "EPD", "RSA", (2026, 6, 18, 16, 0)),
            ("A", "MEX", "KOR", (2026, 6, 19, 1, 0)),
            ("A", "EPD", "MEX", (2026, 6, 25, 1, 0)),
            ("A", "RSA", "KOR", (2026, 6, 25, 1, 0)),

            # GROUP B
            ("B", "CAN", "EPA", (2026, 6, 12, 19, 0)),
            ("B", "QAT", "SUI", (2026, 6, 13, 19, 0)),
            ("B", "SUI", "EPA", (2026, 6, 18, 19, 0)),
            ("B", "CAN", "QAT", (2026, 6, 18, 22, 0)),
            ("B", "SUI", "CAN", (2026, 6, 24, 19, 0)),
            ("B", "EPA", "QAT", (2026, 6, 24, 19, 0)),

            # GROUP C
            ("C", "BRA", "MAR", (2026, 6, 13, 22, 0)),
            ("C", "HAI", "SCO", (2026, 6, 14, 1, 0)),
            ("C", "SCO", "MAR", (2026, 6, 19, 22, 0)),
            ("C", "BRA", "HAI", (2026, 6, 20, 1, 0)),
            ("C", "SCO", "BRA", (2026, 6, 24, 22, 0)),
            ("C", "MAR", "HAI", (2026, 6, 24, 22, 0)),

            # GROUP D
            ("D", "USA", "PAR", (2026, 6, 13, 1, 0)),
            ("D", "AUS", "EPC", (2026, 6, 13, 4, 0)),
            ("D", "EPC", "PAR", (2026, 6, 19, 4, 0)),
            ("D", "USA", "AUS", (2026, 6, 19, 19, 0)),
            ("D", "EPC", "USA", (2026, 6, 26, 2, 0)),
            ("D", "PAR", "AUS", (2026, 6, 26, 2, 0)),

            # GROUP E
            ("E", "GER", "CUW", (2026, 6, 14, 19, 0)),
            ("E", "CIV", "ECU", (2026, 6, 14, 23, 0)),
            ("E", "GER", "CIV", (2026, 6, 20, 20, 0)),
            ("E", "ECU", "CUW", (2026, 6, 21, 0, 0)),
            ("E", "ECU", "GER", (2026, 6, 25, 20, 0)),
            ("E", "CUW", "CIV", (2026, 6, 25, 20, 0)),

            # GROUP F
            ("F", "NED", "JPN", (2026, 6, 14, 20, 0)),
            ("F", "EPB", "TUN", (2026, 6, 15, 2, 0)),
            ("F", "NED", "EPB", (2026, 6, 20, 17, 0)),
            ("F", "TUN", "JPN", (2026, 6, 21, 4, 0)),
            ("F", "JPN", "EPB", (2026, 6, 25, 23, 0)),
            ("F", "TUN", "NED", (2026, 6, 25, 23, 0)),

            # GROUP G
            ("G", "BEL", "EGY", (2026, 6, 15, 19, 0)),
            ("G", "IRN", "NZL", (2026, 6, 16, 1, 0)),
            ("G", "BEL", "IRN", (2026, 6, 21, 19, 0)),
            ("G", "NZL", "EGY", (2026, 6, 22, 1, 0)),
            ("G", "EGY", "IRN", (2026, 6, 27, 0, 0)),
            ("G", "NZL", "BEL", (2026, 6, 27, 3, 0)),

            # GROUP H
            ("H", "ESP", "CPV", (2026, 6, 15, 16, 0)),
            ("H", "KSA", "URU", (2026, 6, 15, 22, 0)),
            ("H", "ESP", "KSA", (2026, 6, 21, 16, 0)),
            ("H", "URU", "CPV", (2026, 6, 21, 22, 0)),
            ("H", "CPV", "KSA", (2026, 6, 27, 0, 0)),
            ("H", "URU", "ESP", (2026, 6, 27, 0, 0)),

            # GROUP I
            ("I", "FRA", "SEN", (2026, 6, 16, 19, 0)),
            ("I", "FP2", "NOR", (2026, 6, 16, 22, 0)),
            ("I", "FRA", "FP2", (2026, 6, 22, 2, 0)),
            ("I", "NOR", "SEN", (2026, 6, 23, 0, 0)),
            ("I", "NOR", "FRA", (2026, 6, 26, 19, 0)),
            ("I", "SEN", "FP2", (2026, 6, 26, 19, 0)),

            # GROUP J
            ("J", "ARG", "ALG", (2026, 6, 17, 1, 0)),
            ("J", "AUT", "JOR", (2026, 6, 17, 4, 0)),
            ("J", "ARG", "AUT", (2026, 6, 22, 17, 0)),
            ("J", "JOR", "ALG", (2026, 6, 23, 3, 0)),
            ("J", "ALG", "AUT", (2026, 6, 28, 2, 0)),
            ("J", "JOR", "ARG", (2026, 6, 28, 2, 0)),

            # GROUP K
            ("K", "POR", "FP1", (2026, 6, 17, 17, 0)),
            ("K", "UZB", "COL", (2026, 6, 18, 2, 0)),
            ("K", "POR", "UZB", (2026, 6, 23, 17, 0)),
            ("K", "COL", "FP1", (2026, 6, 24, 2, 0)),
            ("K", "COL", "POR", (2026, 6, 27, 23, 30)),
            ("K", "FP1", "UZB", (2026, 6, 27, 23, 30)),

            # GROUP L
            ("L", "ENG", "CRO", (2026, 6, 17, 20, 0)),
            ("L", "GHA", "PAN", (2026, 6, 17, 23, 0)),
            ("L", "ENG", "GHA", (2026, 6, 23, 20, 0)),
            ("L", "PAN", "CRO", (2026, 6, 23, 23, 0)),
            ("L", "PAN", "ENG", (2026, 6, 27, 21, 0)),
            ("L", "CRO", "GHA", (2026, 6, 27, 21, 0)),
        ]

        created_count = 0
        for group, home_code, away_code, (y, m, d, h, mi) in group_matches:
            kickoff = aware(y, m, d, h, mi)
            home = teams[home_code]
            away = teams[away_code]

            match, m_created = Match.objects.get_or_create(
                tournament=tournament,
                stage=s1,
                home_team=home,
                away_team=away,
                kickoff=kickoff,
                defaults={
                    "group_name": group,
                },
            )
            if m_created:
                created_count += 1
            else:
                # garante que o grupo está preenchido certo
                if match.group_name != group:
                    match.group_name = group
                    match.save(update_fields=["group_name"])

        self.stdout.write(self.style.SUCCESS(f"{created_count} jogos da fase de grupos criados (demais reaproveitados)."))
        self.stdout.write(self.style.SUCCESS("Seed da Copa 2026 concluída (pontuações e fases sincronizadas)."))
