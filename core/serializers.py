# core/serializers.py

from datetime import timezone
from rest_framework import serializers
from .models import *
from django.contrib.auth import get_user_model

class PSRSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PSRSnapshot
        fields = [
            'snapshot_date',
            'frequency',
            'data',
            'total_actual_cost',
            'total_forecast_cost',
            'total_prognosis_cost',
            'total_budget_cost',
            'overall_balance',
            'overall_balance_percentage',
            'generated_at',
        ]


User = get_user_model()

class SubDepartmentBudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubDepartment
        fields = ['id', 'budget_hours']

    def update(self, instance, validated_data):
        instance.budget_hours = validated_data.get('budget_hours', instance.budget_hours)
        
        # Auto-calculate budget_cost
        dept = instance.department
        project = dept.project
        instance.budget_cost = instance.budget_hours * dept.hourly_rate * project.exchange_rate
        
        # If forecast is not overridden, keep it auto (we'll recalc in snapshot)
        instance.save()
        return instance


class SubDepartmentForecastOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubDepartment
        fields = ['id', 'forecast_hours', 'forecast_override']

    def validate(self, data):
        if not data.get('forecast_override', False):
            raise serializers.ValidationError("forecast_override must be True when using this endpoint")
        if 'forecast_hours' not in data:
            raise serializers.ValidationError("forecast_hours is required when overriding")
        return data

    def update(self, instance, validated_data):
        user = self.context['request'].user
        
        instance.forecast_override = validated_data.get('forecast_override', instance.forecast_override)
        instance.forecast_hours = validated_data.get('forecast_hours', instance.forecast_hours)
        
        # Auto-calculate forecast_cost from hours
        dept = instance.department
        project = dept.project
        instance.forecast_cost = instance.forecast_hours * dept.hourly_rate * project.exchange_rate
        
        # Audit
        instance.forecast_overridden_by = user
        instance.forecast_overridden_at = timezone.now()
        
        instance.save()
        return instance



# core/serializers.py

class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            'co_no',
            'project_name',
            'location',
            'project_manager',
            'project_manager_email',
            'sales_person',
            'sales_person_email',
            'sales_value_foreign_curr',
            'ebit_percentage',      # ← NEW
            'sgna_percentage',      # ← NEW
            'eff_percentage',
            'ter_percentage',
            'currency',
            'exchange_rate',
            # budget is now calculated — removed from input
        ]

    def validate_co_no(self, value):
        if Project.objects.filter(co_no=value).exists():
            raise serializers.ValidationError("A project with this CO number already exists.")
        return value

    def validate(self, data):
        # Ensure required percentages are provided
        required = ['sales_value_foreign_curr', 'ebit_percentage', 'sgna_percentage']
        for field in required:
            if data.get(field) is None or data.get(field) < 0:
                raise serializers.ValidationError({field: "This field is required and must be >= 0."})
        return data





class ProjectBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['co_no', 'project_name', 'project_manager', 'cw_no', 'current_phase', 'settlement_period']

class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['cw_no', 'current_phase', 'settlement_period']

class PSRSnapshotKPISerializer(serializers.ModelSerializer):
    sales_value = serializers.DecimalField(source='project.sales_value', max_digits=15, decimal_places=2)

    class Meta:
        model = PSRSnapshot
        fields = [
            'sales_value',
            'total_budget_cost',
            'ter_value',
            'eff_value',
            'total_actual_cost',
            'total_forecast_cost',
            'total_prognosis_cost',
            'margin',
            'factor',
        ]


class ProjectLatestSnapshotSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(source='id')
    co_no = serializers.CharField()
    project_name = serializers.CharField()
    sales_value = serializers.DecimalField(max_digits=15, decimal_places=2)

    total_budget_cost = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    ter_value = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    eff_value = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_actual_cost = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_forecast_cost = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_prognosis_cost = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    margin = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    factor = serializers.DecimalField(max_digits=8, decimal_places=4, default=0.0)

class MonthlyCumulativeKPISerializer(serializers.Serializer):
    month = serializers.CharField()
    sales_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_budget_cost = serializers.DecimalField(max_digits=18, decimal_places=2)
    ter_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    eff_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_actual_cost = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_forecast_cost = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_prognosis_cost = serializers.DecimalField(max_digits=18, decimal_places=2)
    margin = serializers.DecimalField(max_digits=18, decimal_places=2)
    factor = serializers.DecimalField(max_digits=8, decimal_places=4)





class RKActualLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = RKActualAdjustmentLine
        fields = ['id', 'description', 'amount']

class RKActualAdjustmentSerializer(serializers.ModelSerializer):
    lines = RKActualLineSerializer(many=True)

    class Meta:
        model = RKActualAdjustment
        fields = ['id', 'note', 'adjusted_at', 'adjusted_by', 'lines']

    def create(self, validated_data):
        lines_data = validated_data.pop('lines')
        adjustment = RKActualAdjustment.objects.create(**validated_data)
        for line_data in lines_data:
            RKActualAdjustmentLine.objects.create(adjustment=adjustment, **line_data)
        return adjustment