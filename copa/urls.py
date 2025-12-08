from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    TeamViewSet,
    StageViewSet,
    MatchViewSet,
    BetViewSet,
    ExtraBetViewSet,
    RankingView,
)

router = DefaultRouter()
router.register("teams", TeamViewSet, basename="team")
router.register("stages", StageViewSet, basename="stage")
router.register("matches", MatchViewSet, basename="match")
router.register("bets", BetViewSet, basename="bet")
router.register("extra-bets", ExtraBetViewSet, basename="extra-bet")

urlpatterns = [
    path("", include(router.urls)),
    path("ranking/", RankingView.as_view(), name="ranking"),
]
