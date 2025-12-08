from django.contrib import admin

from .models import (
    Tournament,
    Stage,
    Team,
    Match,
    Bet,
    ExtraResult,
    ExtraBet,
)


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "extras_deadline")


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = (
        "tournament",
        "order",
        "name",
        "deadline",
        "points_exact_score",
        "points_result",
        "points_one_team_goals",
    )
    list_filter = ("tournament", "order")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "tournament",
        "stage",
        "home_team",
        "away_team",
        "kickoff",
        "group_name",
        "home_score",
        "away_score",
    )
    list_filter = ("tournament", "stage", "group_name")


@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = ("user", "match", "home_score", "away_score", "created_at")
    list_filter = ("match__stage",)


@admin.register(ExtraResult)
class ExtraResultAdmin(admin.ModelAdmin):
    list_display = ("tournament", "type", "team", "player_name")


@admin.register(ExtraBet)
class ExtraBetAdmin(admin.ModelAdmin):
    list_display = ("tournament", "user", "type", "team", "player_name", "created_at")
    list_filter = ("tournament", "type")
