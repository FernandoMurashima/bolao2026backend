from django.utils import timezone
from rest_framework import serializers

from .models import (
    Tournament,
    Stage,
    Team,
    Match,
    Bet,
    ExtraBet,
    ExtraType,
)


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name", "code"]


class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = [
            "id",
            "order",
            "name",
            "deadline",
            "points_exact_score",
            "points_result",
            "points_one_team_goals",
        ]


class MatchSerializer(serializers.ModelSerializer):
    home_team = TeamSerializer(read_only=True)
    away_team = TeamSerializer(read_only=True)
    stage = StageSerializer(read_only=True)

    class Meta:
        model = Match
        fields = [
            "id",
            "tournament",
            "stage",
            "home_team",
            "away_team",
            "kickoff",
            "group_name",
            "home_score",
            "away_score",
        ]
        read_only_fields = ["home_score", "away_score", "tournament", "stage"]


class BetSerializer(serializers.ModelSerializer):
    match = MatchSerializer(read_only=True)
    match_id = serializers.PrimaryKeyRelatedField(
        queryset=Match.objects.all(), write_only=True, source="match"
    )
    points = serializers.SerializerMethodField()

    class Meta:
        model = Bet
        fields = [
            "id",
            "match",
            "match_id",
            "home_score",
            "away_score",
            "created_at",
            "updated_at",
            "points",
        ]
    read_only_fields = ["created_at", "updated_at", "points"]

    def get_points(self, obj):
        return obj.calculate_points()

    def validate(self, attrs):
        match = attrs.get("match") or self.instance.match
        now = timezone.now()
        if match.stage.deadline <= now:
            raise serializers.ValidationError(
                "Prazo para palpites desta etapa já encerrou."
            )
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["user"] = user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class ExtraBetSerializer(serializers.ModelSerializer):
    points = serializers.SerializerMethodField()

    class Meta:
        model = ExtraBet
        fields = [
            "id",
            "tournament",
            "type",
            "team",
            "player_name",
            "created_at",
            "points",
        ]
        read_only_fields = ["created_at", "points"]

    def get_points(self, obj):
        return obj.calculate_points()

    def validate(self, attrs):
        tournament = attrs.get("tournament") or self.instance.tournament
        if timezone.now() >= tournament.extras_deadline:
            raise serializers.ValidationError(
                "Prazo para palpites especiais já encerrou."
            )
        type_ = attrs.get("type") or self.instance.type
        if type_ == ExtraType.TOP_SCORER and not attrs.get("player_name"):
            raise serializers.ValidationError(
                {"player_name": "Informe o nome do artilheiro."}
            )
        if type_ != ExtraType.TOP_SCORER and not attrs.get("team"):
            raise serializers.ValidationError(
                {"team": "Selecione a seleção para esse palpite."}
            )
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["user"] = user
        return super().create(validated_data)
