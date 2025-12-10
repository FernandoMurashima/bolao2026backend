from collections import defaultdict

from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Tournament,
    Stage,
    Team,
    Match,
    Bet,
    ExtraBet,
    ExtraType,
)
from .serializers import (
    TeamSerializer,
    StageSerializer,
    MatchSerializer,
    BetSerializer,
    ExtraBetSerializer,
)


class TeamViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Team.objects.all().order_by("name")
    serializer_class = TeamSerializer
    permission_classes = [permissions.AllowAny]


class StageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Stage.objects.all().order_by("order")
    serializer_class = StageSerializer
    permission_classes = [permissions.AllowAny]


class MatchViewSet(viewsets.ModelViewSet):
    """
    /api/copa/matches/

    Aceita filtros flexíveis:
      - ?tournament=ID
      - ?stage=ID
      - ?stage__order=N
      - ?stage_order=N
      - ?stageOrder=N
      - ?group_name=A
    """

    serializer_class = MatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        "tournament": ["exact"],
        "stage__order": ["exact"],
        "stage": ["exact"],
        "group_name": ["exact"],
    }
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        qs = (
            Match.objects.select_related(
                "tournament", "stage", "home_team", "away_team"
            )
            .all()
            .order_by("kickoff", "id")
        )

        params = self.request.query_params

        # torneio
        tournament_id = params.get("tournament")
        if tournament_id:
            qs = qs.filter(tournament_id=tournament_id)

        # por ID de stage (ex.: stage=2)
        stage_id = params.get("stage")
        if stage_id:
            qs = qs.filter(stage_id=stage_id)

        # por ordem da fase (ex.: stage__order=2, stage_order=2, stageOrder=2)
        stage_order = (
            params.get("stage__order")
            or params.get("stage_order")
            or params.get("stageOrder")
        )
        if stage_order:
            qs = qs.filter(stage__order=stage_order)

        # por grupo (só faz sentido na fase de grupos)
        group_name = params.get("group_name")
        if group_name:
            qs = qs.filter(group_name=group_name)

        return qs

    def partial_update(self, request, *args, **kwargs):
        """
        Atualiza APENAS o resultado oficial (home_score / away_score),
        ignorando o fato de o serializer poder ter esses campos como read_only.
        """

        # 🔒 Só superusuário pode alterar resultado oficial
        if not request.user.is_superuser:
            return Response(
                {"detail": "Apenas superusuários podem alterar resultados oficiais."},
                status=403,
            )

        instance = self.get_object()

        home_score = request.data.get("home_score", None)
        away_score = request.data.get("away_score", None)

        # Converte para int ou None
        if home_score in ("", None):
            instance.home_score = None
        else:
            instance.home_score = int(home_score)

        if away_score in ("", None):
            instance.away_score = None
        else:
            instance.away_score = int(away_score)

        instance.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class BetViewSet(viewsets.ModelViewSet):
    serializer_class = BetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Bet.objects.filter(user=self.request.user)
            .select_related(
                "match",
                "match__stage",
                "match__home_team",
                "match__away_team",
            )
            .order_by("match__kickoff")
        )


class ExtraBetViewSet(viewsets.ModelViewSet):
    serializer_class = ExtraBetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tournament_id = self.request.query_params.get("tournament")
        qs = ExtraBet.objects.filter(user=self.request.user)
        if tournament_id:
            qs = qs.filter(tournament_id=tournament_id)
        return qs.select_related("tournament", "team")


class RankingView(APIView):
    """
    GET /api/copa/ranking/?tournament=<id>
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tournament_id = request.query_params.get("tournament")
        tournament = get_object_or_404(Tournament, id=tournament_id)

        bets = (
            Bet.objects.filter(match__tournament=tournament)
            .select_related("user", "match", "match__stage")
        )
        extra_bets = (
            ExtraBet.objects.filter(tournament=tournament)
            .select_related("user")
        )

        data = defaultdict(
            lambda: {
                "user_id": None,
                "username": "",
                "position": 0,
                "total_points": 0,
                "exact_scores": 0,
                "results": 0,
                "stage5_points": 0,
                "extras_points": 0,
                "champion_hit": False,
            }
        )

        # Pontos dos jogos
        for b in bets:
            uid = b.user_id
            if data[uid]["user_id"] is None:
                data[uid]["user_id"] = uid
                data[uid]["username"] = b.user.username

            pts = b.calculate_points()
            data[uid]["total_points"] += pts
            data[uid]["stage5_points"] += b.points_stage5()
            if b.is_exact_score():
                data[uid]["exact_scores"] += 1
            elif b.is_correct_result():
                data[uid]["results"] += 1

        # Pontos dos extras
        for e in extra_bets:
            uid = e.user_id
            if data[uid]["user_id"] is None:
                data[uid]["user_id"] = uid
                data[uid]["username"] = e.user.username
            pts = e.calculate_points()
            data[uid]["total_points"] += pts
            data[uid]["extras_points"] += pts
            if e.type == ExtraType.CHAMPION and pts > 0:
                data[uid]["champion_hit"] = True

        ranking = list(data.values())

        ranking.sort(
            key=lambda x: (
                -x["total_points"],
                -int(x["champion_hit"]),
                -x["exact_scores"],
                -x["results"],
                -x["stage5_points"],
                -x["extras_points"],
            )
        )

        for i, row in enumerate(ranking, start=1):
            row["position"] = i

        return Response(ranking)
