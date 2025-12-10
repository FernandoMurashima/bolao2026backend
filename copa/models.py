from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class Tournament(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateTimeField()
    extras_deadline = models.DateTimeField()

    def __str__(self):
        return self.name


class Stage(models.Model):
    """
    Ordem das fases:

    1 – Fase de grupos
    2 – Round-of-32
    3 – Oitavas (Round-of-16)
    4 – Quartas (Round-of-8)
    5 – Semifinais (Round-of-4)
    6 – 3º lugar + Final
    """
    ORDER_CHOICES = (
        (1, "Fase de grupos"),
        (2, "Round-of-32"),
        (3, "Oitavas de final"),
        (4, "Quartas de final"),
        (5, "Semifinais"),
        (6, "3º lugar + Final"),
    )

    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name="stages"
    )
    order = models.PositiveSmallIntegerField(choices=ORDER_CHOICES)
    name = models.CharField(max_length=50)
    deadline = models.DateTimeField(
        help_text="Data limite para palpites desta etapa (todos os jogos)."
    )

    points_exact_score = models.PositiveIntegerField()
    points_result = models.PositiveIntegerField()
    points_one_team_goals = models.PositiveIntegerField()

    class Meta:
        unique_together = ("tournament", "order")

    def __str__(self):
        return f"{self.get_order_display()} ({self.tournament})"


class Team(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)  # ex.: BRA, ARG

    def __str__(self):
        return f"{self.code} - {self.name}"


class Match(models.Model):
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name="matches"
    )
    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name="matches")
    home_team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="home_matches"
    )
    away_team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="away_matches"
    )
    kickoff = models.DateTimeField()
    group_name = models.CharField(max_length=5, blank=True, null=True)

    # Resultado oficial (90min)
    home_score = models.PositiveSmallIntegerField(blank=True, null=True)
    away_score = models.PositiveSmallIntegerField(blank=True, null=True)

    # Pênaltis – usados só em fases eliminatórias (order >= 2)
    home_penalties = models.PositiveSmallIntegerField(blank=True, null=True)
    away_penalties = models.PositiveSmallIntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.home_team} x {self.away_team} ({self.stage})"

    @property
    def is_finished(self):
        return self.home_score is not None and self.away_score is not None


class Bet(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bets"
    )
    match = models.ForeignKey(
        Match, on_delete=models.CASCADE, related_name="bets"
    )
    home_score = models.PositiveSmallIntegerField()
    away_score = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "match")

    def __str__(self):
        return f"{self.user} - {self.match}"

    def calculate_points(self):
        """
        Regras:
        - Placar exato -> points_exact_score
        - Senão, resultado correto (vitória/empate) -> points_result
        - Senão, gols de pelo menos um time corretos (sem acertar resultado) -> points_one_team_goals
        - Senão -> 0
        """
        if not self.match.is_finished:
            return 0

        stage = self.match.stage
        ah = self.match.home_score
        aa = self.match.away_score
        ph = self.home_score
        pa = self.away_score

        # Placar exato
        if ah == ph and aa == pa:
            return stage.points_exact_score

        # Resultado real
        real_diff = ah - aa
        pred_diff = ph - pa

        real_sign = 0 if real_diff == 0 else (1 if real_diff > 0 else -1)
        pred_sign = 0 if pred_diff == 0 else (1 if pred_diff > 0 else -1)

        # Resultado (vitória/empate/derrota)
        if real_sign == pred_sign:
            return stage.points_result

        # Não acertou resultado, mas acertou gols de pelo menos um time
        if ah == ph or aa == pa:
            return stage.points_one_team_goals

        return 0

    def is_exact_score(self):
        if not self.match.is_finished:
            return False
        return (
            self.match.home_score == self.home_score
            and self.match.away_score == self.away_score
        )

    def is_correct_result(self):
        if not self.match.is_finished:
            return False
        ah = self.match.home_score
        aa = self.match.away_score
        ph = self.home_score
        pa = self.away_score
        real_diff = ah - aa
        pred_diff = ph - pa
        real_sign = 0 if real_diff == 0 else (1 if real_diff > 0 else -1)
        pred_sign = 0 if pred_diff == 0 else (1 if pred_diff > 0 else -1)
        return real_sign == pred_sign and not self.is_exact_score()

    def points_stage5(self):
        """
        Continua o nome, mas agora considera a última fase (order=6).
        """
        if self.match.stage.order != 6:
            return 0
        return self.calculate_points()


class ExtraType(models.TextChoices):
    CHAMPION = "CHAMPION", "Campeã"
    RUNNER_UP = "RUNNER_UP", "Vice-campeã"
    THIRD_PLACE = "THIRD_PLACE", "3º lugar"
    MOST_RED = "MOST_RED", "Mais cartões vermelhos"
    MOST_YELLOW = "MOST_YELLOW", "Mais cartões amarelos"
    FEWEST_GOALS_CONCEDED = "FEWEST_GC", "Menos gols sofridos"
    MOST_GOALS_CONCEDED = "MOST_GC", "Mais gols sofridos"
    FEWEST_GOALS_SCORED = "FEWEST_GF", "Menos gols marcados"
    MOST_GOALS_SCORED = "MOST_GF", "Mais gols marcados"
    TOP_SCORER = "TOP_SCORER", "Artilheiro (jogador)"


EXTRA_POINTS = {
    ExtraType.CHAMPION: 500,
    ExtraType.RUNNER_UP: 250,
    ExtraType.THIRD_PLACE: 125,
    ExtraType.MOST_RED: 100,
    ExtraType.MOST_YELLOW: 100,
    ExtraType.FEWEST_GOALS_CONCEDED: 50,
    ExtraType.MOST_GOALS_CONCEDED: 250,
    ExtraType.FEWEST_GOALS_SCORED: 250,
    ExtraType.MOST_GOALS_SCORED: 300,
    ExtraType.TOP_SCORER: 300,
}


class ExtraResult(models.Model):
    """
    Gabarito dos extras.
    """
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name="extra_results"
    )
    type = models.CharField(max_length=20, choices=ExtraType.choices)
    team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True
    )
    player_name = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ("tournament", "type")

    def __str__(self):
        return f"{self.get_type_display()} - {self.team or self.player_name}"


class ExtraBet(models.Model):
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name="extra_bets"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="extra_bets"
    )
    type = models.CharField(max_length=20, choices=ExtraType.choices)
    team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True
    )
    player_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tournament", "user", "type")

    def __str__(self):
        return f"{self.user} - {self.get_type_display()}"

    def calculate_points(self):
        try:
            gabarito = ExtraResult.objects.get(
                tournament=self.tournament, type=self.type
            )
        except ExtraResult.DoesNotExist:
            return 0

        if self.type == ExtraType.TOP_SCORER:
            if (
                self.player_name
                and gabarito.player_name
                and self.player_name.strip().lower()
                == gabarito.player_name.strip().lower()
            ):
                return EXTRA_POINTS[self.type]
            return 0
        else:
            if self.team and gabarito.team and self.team_id == gabarito.team_id:
                return EXTRA_POINTS[self.type]
            return 0
