from import_export.admin import ImportExportModelAdmin
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from core.models import *


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'co_no',
        'project_name',
        'location',
        'project_manager',
        'currency',
        'exchange_rate_display',
        'sales_value_display',
        'ebit_percentage',
        'sgna_percentage',
        'hk_display',
        'actual_budget_display',
        'direct_margin_value_display',
        'direct_margin_percentage_display',
        'factor_display',
        'created_at',
    )
    list_filter = (
        'currency',
        'location',
        'created_at',
        'ebit_percentage',
        'sgna_percentage',
    )
    search_fields = (
        'co_no',
        'project_name',
        'project_manager',
        'sales_person',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        # All calculated fields
        'ebit_value_display',
        'cost_with_sgna_display',
        'hk_display',
        'direct_margin_value_display',
        'direct_margin_percentage_display',
        'ter_value_display',
        'eff_value_display',
        'actual_budget_display',
        'factor_display',
        'budget_display',  # legacy, same as actual_budget
    )

    fieldsets = (
        ('Project Identification', {
            'fields': ('co_no', 'project_name', 'location')
        }),
        ('Personnel', {
            'fields': ('project_manager', 'project_manager_email', 'sales_person', 'sales_person_email')
        }),
        ('Financial Planning Inputs', {
            'fields': (
                'sales_value_foreign_curr',
                'ebit_percentage',
                'sgna_percentage',
                'eff_percentage',
                'ter_percentage',
            ),
            'description': 'Enter percentages. All other financial values are auto-calculated.'
        }),
        ('Calculated Financial KPIs (Read-only)', {
            'fields': (
                'sales_value',
                'ebit_value_display',
                'cost_with_sgna_display',
                'hk_display',
                'direct_margin_value_display',
                'direct_margin_percentage_display',
                'ter_value_display',
                'eff_value_display',
                'actual_budget_display',
                'factor_display',
                'budget_display',  # legacy field
            ),
            'classes': ('collapse',),
        }),
        ('Currency Settings', {
            'fields': ('currency', 'exchange_rate')
        }),
        ('Project Status', {
            'fields': ('cw_no', 'current_phase', 'settlement_period')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # === Display Methods ===
    def sales_value_display(self, obj):
        return f"₹{obj.sales_value:,.2f}" if obj.sales_value else "-"
    sales_value_display.short_description = "Sales Value"

    def ebit_value_display(self, obj):
        return f"₹{obj.ebit_value:,.2f}" if obj.ebit_value else "-"
    ebit_value_display.short_description = "EBIT Value (₹)"
    
    def sgna_value_display(self, obj):
        return f"₹{obj.sgna_value:,.2f}" if obj.sgna_value else "-"
    sgna_value_display.short_description = "SGNA Value (₹)"

    def cost_with_sgna_display(self, obj):
        return f"₹{obj.cost_with_sgna:,.2f}" if obj.cost_with_sgna else "-"
    cost_with_sgna_display.short_description = "Cost with SGNA (₹)"

    def hk_display(self, obj):
        return f"₹{obj.hk:,.2f}" if obj.hk else "-"
    hk_display.short_description = "HK (₹)"

    def direct_margin_value_display(self, obj):
        return f"₹{obj.direct_margin_value:,.2f}" if obj.direct_margin_value else "-"
    direct_margin_value_display.short_description = "Direct Margin Value (₹)"

    def direct_margin_percentage_display(self, obj):
        return f"{obj.direct_margin_percentage:.4f}%" if obj.direct_margin_percentage else "-"
    direct_margin_percentage_display.short_description = "Direct Margin %"

    def ter_value_display(self, obj):
        return f"₹{obj.ter_value:,.2f}" if obj.ter_value else "-"
    ter_value_display.short_description = "TER Value (₹)"

    def eff_value_display(self, obj):
        return f"₹{obj.eff_value:,.2f}" if obj.eff_value else "-"
    eff_value_display.short_description = "EFF Value (₹)"

    def actual_budget_display(self, obj):
        return f"₹{obj.actual_budget:,.2f}" if obj.actual_budget else "-"
    actual_budget_display.short_description = "Actual Budget (₹)"

    def factor_display(self, obj):
        return f"{obj.factor:.4f}" if obj.factor else "-"
    factor_display.short_description = "Factor"

    def budget_display(self, obj):
        return f"₹{obj.budget:,.2f}" if obj.budget else "-"
    budget_display.short_description = "Budget"

    def exchange_rate_display(self, obj):
        return f"{obj.exchange_rate:.4f}"
    exchange_rate_display.short_description = "Exchange Rate to INR"


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = (
        'department_link',
        'project_link',
        'hourly_rate_display',
        'budget_cost_display',           # ← NEW: Show actual stored cost
        'budget_hours_display',          # ← Optional: show derived hours
    )
    list_filter = ('name', 'project__co_no', 'project__currency')
    search_fields = ('project__co_no', 'project__project_name', 'name')
    raw_id_fields = ('project',)
    readonly_fields = (
        'created_at',
        'updated_at',
        'budget_cost_display',
        'budget_hours_display',
    )

    fieldsets = (
        ('Department Details', {
            'fields': ('project', 'name', 'hourly_rate')
        }),
        ('Budget (Cost-based — Primary)', {
            'fields': ('budget_cost_display',),
            'description': 'Budget cost in INR — auto-calculated from sub-departments. Hours are derived.'
        }),
        ('Derived Hours (Read-only)', {
            'fields': ('budget_hours_display',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def budget_cost_display(self, obj):
        return f"₹{obj.budget_cost:,.2f}"
    budget_cost_display.short_description = "Budget Cost (INR)"

    def budget_hours_display(self, obj):
        if obj.budget_cost and obj.hourly_rate and obj.project.exchange_rate > 0:
            hours = obj.budget_cost / (obj.hourly_rate * obj.project.exchange_rate)
            return f"{hours:,.2f} hrs"
        return "0.00 hrs"
    budget_hours_display.short_description = "Budget Hours (Derived)"

    def hourly_rate_display(self, obj):
        return f"{obj.hourly_rate:,.2f} {obj.project.currency}"
    hourly_rate_display.short_description = "Hourly Rate"

    def department_link(self, obj):
        url = reverse("admin:core_department_change", args=[obj.pk])
        return format_html('<a href="{}"><strong>{}</strong></a>', url, obj.get_name_display())
    department_link.short_description = "Department"

    def project_link(self, obj):
        url = reverse("admin:core_project_change", args=[obj.project.pk])
        return format_html('<a href="{}">{}</a>', url, obj.project.co_no)
    project_link.short_description = "Project"

@admin.register(SubDepartment)
class SubDepartmentAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'role_descrptn',
        'inkrement',
        'baseline_budget_cost_display',     # ← Updated: show baseline cost
        'budget_cost_display',              # ← Primary: current cost in INR
        'budget_hours_display',             # ← Derived hours (read-only)
        'forecast_override',
        'current_forecast_cost_display',
        'forecast_overridden_by',
        'department_link',
        'project_link',
    )
    list_filter = (
        'department__name',
        'department__project__co_no',
        'department__project__currency',
        'forecast_override'
    )
    search_fields = (
        'code',
        'role_descrptn',
        'inkrement',
        'department__project__co_no',
        'department__project__project_name',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'current_forecast_cost_display',
        'forecast_overridden_at',
        'baseline_budget_cost_display',
        'budget_hours_display',             # ← Hours now read-only
        'calculated_budget_cost_inr',       # ← Legacy, kept if needed
    )

    fieldsets = (
        ('Sub-Department Details', {
            'fields': ('department', 'code', 'role_descrptn', 'inkrement')
        }),
        ('Baseline Budget (Original - Read Only)', {
            'fields': ('baseline_budget_cost_display',),
            'description': 'Original budgeted cost (INR) set at project creation. Never changes.',
            'classes': ('collapse',)
        }),
        ('Current Budget (INR)', {
            'fields': ('budget_cost',),
            'description': 'Current budgeted cost in INR — primary input. Hours are auto-calculated.'
        }),
        ('Derived Hours (Read-only)', {
            'fields': ('budget_hours_display',),
            'classes': ('collapse',)
        }),
        ('Legacy Calculated Cost (Read-only)', {
            'fields': ('calculated_budget_cost_inr',),
            'classes': ('collapse',)
        }),
        ('Forecast Override', {
            'fields': (
                'forecast_override',
                'forecast_hours',
                'forecast_cost',
                'forecast_overridden_by',
                'forecast_overridden_at',
            ),
            'description': 'Enable override to manually set forecast. Disable to use auto formula.',
        }),
        ('Current Forecast Preview (Read-only)', {
            'fields': ('current_forecast_cost_display',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # === Display Methods ===
    def baseline_budget_cost_display(self, obj):
        cost = obj.baseline_budget_hours * obj.department.hourly_rate * obj.department.project.exchange_rate
        return f"₹{cost:,.2f}"
    baseline_budget_cost_display.short_description = "Baseline Budget Cost (INR)"

    def budget_cost_display(self, obj):
        return f"₹{obj.budget_cost:,.2f}"
    budget_cost_display.short_description = "Current Budget Cost (INR)"

    def budget_hours_display(self, obj):
        return f"{obj.budget_hours:,.2f} hrs"
    budget_hours_display.short_description = "Current Budget Hours (Derived)"

    def calculated_budget_cost_inr(self, obj):
        # Legacy — kept for backward compatibility
        if obj.budget_hours and obj.department and obj.department.hourly_rate:
            cost = obj.budget_hours * obj.department.hourly_rate * obj.department.project.exchange_rate
            return f"₹{cost:,.2f}"
        return "₹0.00"
    calculated_budget_cost_inr.short_description = "Legacy Budget Cost (INR)"

    def current_forecast_cost_display(self, obj):
        if obj.forecast_override:
            return f"Manual: ₹{obj.forecast_cost:,.2f}"
        else:
            return "Auto-calculated in snapshot"
    current_forecast_cost_display.short_description = "Current Forecast Cost (INR)"

    def department_link(self, obj):
        return format_html(
            '<a href="/admin/core/department/{pk}/change/">{name}</a>',
            pk=obj.department.pk,
            name=obj.department.get_name_display()
        )
    department_link.short_description = "Department"

    def project_link(self, obj):
        return obj.department.project.co_no
    project_link.short_description = "Project"


@admin.register(TimesheetEntry)
class TimesheetEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'project_link', 'emp_cd', 'emp_name', 'role_description', 'hours', 'co_no')
    list_filter = ('date', 'co_no', 'role_description')
    search_fields = ('emp_cd', 'emp_name', 'role_description', 'co_no')
    readonly_fields = ('imported_at', 'updated_at')
    date_hierarchy = 'date'
    list_per_page = 50

    def project_link(self, obj):
        try:
            project = Project.objects.get(co_no=obj.co_no[:5])
            url = reverse("admin:core_project_change", args=[project.id])
            return format_html('<a href="{}"><strong>{}</strong></a>', url, project.co_no)
        except Project.DoesNotExist:
            return obj.co_no[:5] + " (Not Found)"
    project_link.short_description = "Project"


@admin.register(POData)
class PODataAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('co_no', 'project_link', 'mat_code', 'formatted_value', 'project_name')
    list_filter = ('mat_code',)
    search_fields = ('co_no', 'mat_code', 'project_name')
    readonly_fields = ('imported_at', 'updated_at')
    list_per_page = 50

    def project_link(self, obj):
        try:
            project = Project.objects.get(co_no=obj.co_no[:5])
            url = reverse("admin:core_project_change", args=[project.id])
            return format_html('<a href="{}"><strong>{}</strong></a>', url, project.co_no)
        except Project.DoesNotExist:
            return obj.co_no[:5] + " (Not Found)"
    project_link.short_description = "Project"

    def formatted_value(self, obj):
        return f"₹{obj.po_value_inr:,.2f}"
    formatted_value.short_description = "PO Value (INR)"


@admin.register(CostCategory)
class CostCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'mat_code')
    search_fields = ('code', 'name', 'mat_code')
    list_filter = ('code',)
    readonly_fields = ('name',)

    fieldsets = (
        ('Category Details', {
            'fields': ('code', 'mat_code', 'name')
        }),
    )

    def has_add_permission(self, request):
        # Allow adding only if no categories exist (to prevent duplicates)
        return CostCategory.objects.count() == 0 or request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        # Prevent accidental deletion of fixed categories
        return False




class RKActualAdjustmentLineInline(admin.TabularInline):
    model = RKActualAdjustmentLine
    extra = 1
    fields = ('description', 'amount')
    readonly_fields = ('amount_display',)

    def amount_display(self, obj):
        return f"₹{obj.amount:,.2f}"
    amount_display.short_description = "Amount (INR)"


class RKActualAdjustmentInline(admin.TabularInline):
    model = RKActualAdjustment
    extra = 0
    fields = ('note', 'adjusted_by', 'adjusted_at', 'total_amount')
    readonly_fields = ('adjusted_by', 'adjusted_at', 'total_amount')
    inlines = [RKActualAdjustmentLineInline]  # Nested lines
    show_change_link = True

    def total_amount(self, obj):
        if obj.pk:
            total = sum(line.amount for line in obj.lines.all())
            return format_html('<strong>₹{:,}</strong>', total)
        return "-"
    total_amount.short_description = "Total Amount (INR)"



@admin.register(RKActualAdjustment)
class RKActualAdjustmentWithLinesAdmin(admin.ModelAdmin):
    list_display = (
        'project_co_no',
        'adjusted_by',
        'note_preview',
        'total_amount',
        'adjusted_at',
    )
    list_filter = ('project_cost_category__project__co_no', 'adjusted_by', 'adjusted_at')
    search_fields = (
        'project_cost_category__project__co_no',
        'note',
    )
    date_hierarchy = 'adjusted_at'
    inlines = [RKActualAdjustmentLineInline]  # ← This is the key feature
    readonly_fields = ('adjusted_at', 'adjusted_by', 'total_amount_display')

    fieldsets = (
        ('Adjustment Info', {
            'fields': ('project_cost_category', 'note', 'adjusted_by', 'adjusted_at')
        }),
        ('Total', {
            'fields': ('total_amount_display',),
        }),
    )

    def project_co_no(self, obj):
        return obj.project_cost_category.project.co_no
    project_co_no.short_description = "Project"
    project_co_no.admin_order_field = 'project_cost_category__project__co_no'

    def note_preview(self, obj):
        return (obj.note[:50] + '...') if len(obj.note) > 50 else obj.note
    note_preview.short_description = "Note"

    def total_amount_display(self, obj):
        total = sum(line.amount for line in obj.lines.all())
        return format_html('<strong>₹{:,}</strong>', total)
    total_amount_display.short_description = "Total Amount (INR)"

    def total_amount(self, obj):
        return sum(line.amount for line in obj.lines.all())
    total_amount.short_description = "Total Amount"





@admin.register(ProjectCostCategory)
class ProjectCostCategoryAdmin(admin.ModelAdmin):
    list_display = (
        'cost_category_link',
        'project_link',
        'cost_category_display',
        'baseline_budget_cost_display',
        'budget_cost_display',
        'actual_override',                    # ← NEW
        'current_actual_cost_display',        # ← NEW
        'forecast_override',
        'current_forecast_cost_display',
        'forecast_overridden_by',
        'updated_at'
    )
    list_filter = (
        'project__co_no',
        'cost_category__code',
        'forecast_override',
        'actual_override',                    # ← NEW filter
    )
    search_fields = (
        'project__co_no',
        'project__project_name',
        'cost_category__code',
        'cost_category__name'
    )
    raw_id_fields = ('project',)
    readonly_fields = (
        'created_at',
        'updated_at',
        'current_forecast_cost_display',
        'forecast_overridden_at',
        'baseline_budget_cost_display',
        'current_actual_cost_display',         # ← NEW
    )
    inlines = []  # Will conditionally add RK inline

    fieldsets = (
        ('Project & Category', {
            'fields': ('project', 'cost_category')
        }),
        ('Baseline Budget (Original - Read Only)', {
            'fields': ('baseline_budget_cost_display',),
            'description': 'Original budgeted cost set at project creation. Never changes.',
            'classes': ('collapse',)
        }),
        ('Current Budget (INR)', {
            'fields': ('budget_cost',),
            'description': 'Current budgeted cost — can be updated via budget update API'
        }),
        ('RK Actual Override (Travel Costs Only)', {
            'fields': ('actual_override', 'current_actual_cost_display'),
            'description': 'Enable to manually enter RK actuals instead of using PO data.',
            'classes': ('collapse',)
        }),
        ('Forecast Override (Optional)', {
            'fields': (
                'forecast_override',
                'forecast_cost',
                'forecast_overridden_by',
                'forecast_overridden_at',
            ),
            'description': 'Enable override to manually set forecast cost. Disable to use auto formula (Current Budget - Actual).',
        }),
        ('Current Forecast Preview (Read-only)', {
            'fields': ('current_forecast_cost_display',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_inlines(self, request, obj=None):
        """Show RK actual adjustments inline only if this is RK category"""
        if obj and obj.cost_category.code == 'RK':
            return [RKActualAdjustmentInline]
        return []

    def cost_category_link(self, obj):
        url = reverse("admin:core_projectcostcategory_change", args=[obj.pk])
        return format_html('<a href="{}"><strong>{}</strong></a>', url, obj.cost_category.code)
    cost_category_link.short_description = "Category Code"

    def project_link(self, obj):
        url = reverse("admin:core_project_change", args=[obj.project.pk])
        return format_html('<a href="{}">{}</a>', url, obj.project.co_no)
    project_link.short_description = "Project"

    def cost_category_display(self, obj):
        return obj.cost_category.get_code_display()
    cost_category_display.short_description = "Category"

    def baseline_budget_cost_display(self, obj):
        return f"₹{obj.baseline_budget_cost:,.2f}"
    baseline_budget_cost_display.short_description = "Baseline Budget (INR)"

    def budget_cost_display(self, obj):
        return f"₹{obj.budget_cost:,.2f}"
    budget_cost_display.short_description = "Current Budget (INR)"

    def current_actual_cost_display(self, obj):
        if obj.cost_category.code == 'RK' and obj.actual_override:
            total = sum(
                line.amount for adj in obj.rk_actual_adjustments.all()
                for line in adj.lines.all()
            )
            return format_html('<strong style="color: green;">Manual: ₹{}</strong>', f"{total:,.2f}")
        else:
            return "From PO data (calculated in snapshot)"
    current_actual_cost_display.short_description = "Current Actual Cost"

    def current_forecast_cost_display(self, obj):
        if obj.forecast_override:
            return f"Manual: ₹{obj.forecast_cost:,.2f}"
        else:
            return "Auto: Current Budget - Actual (calculated in snapshot)"
    current_forecast_cost_display.short_description = "Current Forecast Cost (INR)"


@admin.register(PSRSnapshot)
class PSRSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'project_link',  # Now links to the PSRSnapshot change page
        'snapshot_date',
        'frequency',
        'total_actual_cost_display',
        'total_forecast_cost_display',
        'total_prognosis_cost_display',
        'total_budget_cost_display',
        'generated_at_display',
    )
    list_filter = ('frequency', 'snapshot_date', 'project__co_no', 'project__currency')
    search_fields = ('project__co_no', 'project__project_name')
    date_hierarchy = 'snapshot_date'
    readonly_fields = (
        'generated_at', 'generated_by', 'data',
        'total_actual_cost', 'total_forecast_cost',
        'total_prognosis_cost', 'total_budget_cost',
        'eff_value', 'ter_value', 'sum_prognosis',
        'margin', 'factor',
    )

    fieldsets = (
        ('Snapshot Info', {'fields': ('project', 'snapshot_date', 'frequency')}),
        ('Summary (INR)', {
            'fields': (
                'total_actual_cost',
                'total_forecast_cost',
                'total_prognosis_cost',
                'total_budget_cost'
            )
        }),
        ('KPI Fields', {
            'fields': (
                'eff_value',
                'ter_value',
                'sum_prognosis',
                'margin',
                'factor',
            )
        }),
        ('Data (JSON)', {'fields': ('data',), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('generated_at', 'generated_by'), 'classes': ('collapse',)}),
    )

    def project_link(self, obj):
        # Now links to the current PSRSnapshot change page
        url = reverse("admin:core_psrsnapshot_change", args=[obj.pk])
        return format_html('<a href="{}"><strong>{}</strong></a>', url, obj.project.co_no)
    project_link.short_description = "Project CO No"
    project_link.admin_order_field = 'project__co_no'

    def total_actual_cost_display(self, obj):
        return f"₹{obj.total_actual_cost:,.2f}"
    total_actual_cost_display.short_description = "Actual Cost"

    def total_forecast_cost_display(self, obj):
        return f"₹{obj.total_forecast_cost:,.2f}"
    total_forecast_cost_display.short_description = "Forecast Cost"

    def total_prognosis_cost_display(self, obj):
        return f"₹{obj.total_prognosis_cost:,.2f}"
    total_prognosis_cost_display.short_description = "Prognosis Cost"

    def total_budget_cost_display(self, obj):
        return f"₹{obj.total_budget_cost:,.2f}"
    total_budget_cost_display.short_description = "Budget Cost"

    def generated_at_display(self, obj):
        return obj.generated_at.strftime("%Y-%m-%d %H:%M")
    generated_at_display.short_description = "Generated At"





@admin.register(SubDepartmentBudgetAdjustment)
class SubDepartmentBudgetAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        'sub_department',
        'adjustment_date',
        'adjusted_by',
        'previous_budget_hours',
        'new_budget_hours',
        'note_preview',
    )
    list_filter = ('adjustment_date', 'adjusted_by', 'sub_department__department__project__co_no')
    search_fields = (
        'sub_department__code',
        'sub_department__department__project__co_no',
        'note',
        'adjusted_by__username',
    )
    readonly_fields = (
        'adjustment_date',
        'adjusted_by',
        'previous_budget_hours',
        'new_budget_hours',
        'created_at',
    )
    date_hierarchy = 'adjustment_date'

    fieldsets = (
        ('Adjustment Overview', {
            'fields': ('sub_department', 'adjustment_date', 'adjusted_by')
        }),
        ('Budget Hours Change', {
            'fields': ('previous_budget_hours', 'new_budget_hours')
        }),
        ('Reason', {
            'fields': ('note',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def note_preview(self, obj):
        if len(obj.note) > 60:
            return obj.note[:60] + "..."
        return obj.note or "-"
    note_preview.short_description = "Note"

    def has_add_permission(self, request):
        # Created only via API
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser



# core/admin.py

@admin.register(ProjectCostCategoryBudgetAdjustment)
class ProjectCostCategoryBudgetAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        'project_cost_category',
        'adjustment_date',
        'adjusted_by',
        'previous_budget_cost_display',
        'new_budget_cost_display',
        'note_preview',
    )
    list_filter = ('adjustment_date', 'adjusted_by', 'project_cost_category__project__co_no')
    search_fields = (
        'project_cost_category__cost_category__code',
        'project_cost_category__project__co_no',
        'note',
        'adjusted_by__username',
    )
    readonly_fields = (
        'adjustment_date',
        'adjusted_by',
        'previous_budget_cost',
        'new_budget_cost',
        'created_at',
    )
    date_hierarchy = 'adjustment_date'

    fieldsets = (
        ('Adjustment Overview', {
            'fields': ('project_cost_category', 'adjustment_date', 'adjusted_by')
        }),
        ('Budget Cost Change (INR)', {
            'fields': ('previous_budget_cost', 'new_budget_cost')
        }),
        ('Reason', {
            'fields': ('note',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def previous_budget_cost_display(self, obj):
        return f"₹{obj.previous_budget_cost:,.2f}"
    previous_budget_cost_display.short_description = "Previous Budget"

    def new_budget_cost_display(self, obj):
        return f"₹{obj.new_budget_cost:,.2f}"
    new_budget_cost_display.short_description = "New Budget"

    def note_preview(self, obj):
        if len(obj.note) > 60:
            return obj.note[:60] + "..."
        return obj.note or "-"
    note_preview.short_description = "Note"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser






#---------------------------#
# Forecast Override Section #
#---------------------------#

@admin.register(ForecastAdjustment)
class ForecastAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        'sub_department',
        'adjustment_date',
        'adjusted_by',
        'previous_forecast_hours',
        'new_forecast_hours',
        'note_preview',
    )
    list_filter = ('adjustment_date', 'adjusted_by', 'sub_department__department__project__co_no')
    search_fields = (
        'sub_department__code',
        'sub_department__department__project__co_no',
        'note',
        'adjusted_by__username',
    )
    readonly_fields = (
        'adjustment_date',
        'adjusted_by',
        'previous_forecast_hours',
        'new_forecast_hours',
        'created_at',
    )
    date_hierarchy = 'adjustment_date'

    fieldsets = (
        ('Adjustment Overview', {
            'fields': ('sub_department', 'adjustment_date', 'adjusted_by')
        }),
        ('Forecast Change', {
            'fields': ('previous_forecast_hours', 'new_forecast_hours')
        }),
        ('Reason', {
            'fields': ('note',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def note_preview(self, obj):
        if len(obj.note) > 50:
            return obj.note[:50] + "..."
        return obj.note
    note_preview.short_description = "Note"

    def has_add_permission(self, request):
        # Adjustments are created via API, not manually in admin
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(ForecastAdjustmentLine)
class ForecastAdjustmentLineAdmin(admin.ModelAdmin):
    list_display = ('adjustment', 'description', 'hours')
    list_filter = ('adjustment__sub_department__department__project__co_no', 'adjustment__adjustment_date')
    search_fields = ('description', 'adjustment__sub_department__code')

    readonly_fields = ('adjustment', 'description', 'hours')

    fieldsets = (
        ('Line Item', {
            'fields': ('adjustment', 'description', 'hours')
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser







@admin.register(MaterialForecastAdjustment)
class MaterialForecastAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        'project_cost_category',
        'adjustment_date',
        'adjusted_by',
        'previous_forecast_cost_display',
        'new_forecast_cost_display',
        'note_preview',
    )
    list_filter = ('adjustment_date', 'adjusted_by', 'project_cost_category__project__co_no')
    search_fields = (
        'project_cost_category__project__co_no',
        'project_cost_category__cost_category__code',
        'note',
        'adjusted_by__username',
    )
    readonly_fields = (
        'adjustment_date',
        'adjusted_by',
        'previous_forecast_cost',
        'new_forecast_cost',
        'created_at',
    )
    date_hierarchy = 'adjustment_date'

    fieldsets = (
        ('Adjustment Overview', {
            'fields': ('project_cost_category', 'adjustment_date', 'adjusted_by')
        }),
        ('Forecast Change (INR)', {
            'fields': ('previous_forecast_cost', 'new_forecast_cost')
        }),
        ('Reason', {
            'fields': ('note',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def previous_forecast_cost_display(self, obj):
        return f"₹{obj.previous_forecast_cost:,.2f}"
    previous_forecast_cost_display.short_description = "Previous Forecast"

    def new_forecast_cost_display(self, obj):
        return f"₹{obj.new_forecast_cost:,.2f}"
    new_forecast_cost_display.short_description = "New Forecast"

    def note_preview(self, obj):
        if len(obj.note) > 60:
            return obj.note[:60] + "..."
        return obj.note
    note_preview.short_description = "Note"

    def has_add_permission(self, request):
        # Created only via API
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(MaterialForecastAdjustmentLine)
class MaterialForecastAdjustmentLineAdmin(admin.ModelAdmin):
    list_display = ('adjustment', 'description', 'amount_display')
    list_filter = ('adjustment__project_cost_category__project__co_no', 'adjustment__adjustment_date')
    search_fields = ('description', 'adjustment__project_cost_category__project__co_no')

    readonly_fields = ('adjustment', 'description', 'amount')

    fieldsets = (
        ('Line Item', {
            'fields': ('adjustment', 'description', 'amount')
        }),
    )

    def amount_display(self, obj):
        return f"₹{obj.amount:,.2f}"
    amount_display.short_description = "Amount"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    # Show lines inline in the adjustment admin (recommended)
    class Meta:
        verbose_name_plural = "Material Forecast Adjustment Lines"
