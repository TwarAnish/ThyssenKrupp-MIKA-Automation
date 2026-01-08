# core/models.py

from django.core.validators import MinValueValidator
from django.db import models
from decimal import Decimal

# Updated Project model in core/models.py

class Project(models.Model):
    CURRENCY_CHOICES = [
        ('INR', 'Indian Rupee (₹)'),
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'British Pound (£)'),
        ('CHF', 'Swiss Franc (CHF)'),
    ]

    co_no = models.CharField(max_length=50, unique=True)
    project_name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True, null=True)
    project_manager = models.CharField(max_length=100)
    project_manager_email = models.EmailField()
    sales_person = models.CharField(max_length=100)
    sales_person_email = models.EmailField()
    
    sales_value_foreign_curr = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.00)], default=0.00)
    sales_value = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.00)], editable=True)

    cw_no = models.CharField(max_length=100, blank=True, null=True)
    current_phase = models.CharField(max_length=100, blank=True, null=True)
    settlement_period = models.CharField(max_length=100, blank=True, null=True)

    # NEW: Input Percentages (Manual Entry)
    ebit_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0.00)], verbose_name="EBIT (%)"
    )
    sgna_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0.00)], verbose_name="SGNA (%)"
    )
    eff_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0.00)], verbose_name="EFF (%)"
    )
    ter_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0.00)], verbose_name="TER (%)"
    )

    # Currency
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='INR')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000, validators=[MinValueValidator(0.0001)])

    # === CALCULATED FIELDS (Auto-filled on save) ===
    ebit_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, editable=False)
    sgna_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, editable=False)
    cost_with_sgna = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, editable=False)
    hk = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, editable=False, verbose_name="HK (House Keeping)")
    direct_margin_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, editable=False)
    direct_margin_percentage = models.DecimalField(max_digits=8, decimal_places=4, default=0.0000, editable=False)
    ter_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, editable=False)
    eff_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, editable=False)
    actual_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, editable=False)
    factor = models.DecimalField(max_digits=8, decimal_places=3, default=0.0000, editable=False)

    # Legacy field — now auto-calculated (kept for compatibility)
    budget = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['co_no']
        verbose_name = "Project"
        verbose_name_plural = "Projects"

    def __str__(self):
        return f"{self.co_no} - {self.project_name}"


    def save(self, *args, **kwargs):
        # Calculate sales_value in INR from foreign currency
        if self.sales_value_foreign_curr and self.exchange_rate:
            self.sales_value = self.sales_value_foreign_curr * self.exchange_rate

        # Only calculate if percentages and sales_value are set
        if self.sales_value and self.sales_value > 0:

            # EBIT Value
            self.ebit_value = self.sales_value * (self.ebit_percentage / Decimal('100'))

            # SGNA Value
            self.sgna_value = self.sales_value * (self.sgna_percentage / Decimal('100'))

            # Cost with SGNA
            self.cost_with_sgna = self.sales_value - self.ebit_value

            # HK = Cost with SGNA / (1 + SGNA%)
            self.hk = self.cost_with_sgna - self.sgna_value

            # Direct Margin
            self.direct_margin_value = self.sales_value - self.hk
            self.direct_margin_percentage = (self.direct_margin_value / self.sales_value) * Decimal('100') if self.sales_value else Decimal('0')

            # TER & EFF Values
            self.ter_value = self.sales_value * (self.ter_percentage / Decimal('100'))
            self.eff_value = self.sales_value * (self.eff_percentage / Decimal('100'))

            # Actual Budget = HK - TER - EFF
            self.actual_budget = self.hk - self.ter_value - self.eff_value

            # Factor = Sales / HK
            self.factor = self.sales_value / self.hk if self.hk > 0 else Decimal('0')

            # Legacy budget field — now equals Actual Budget
            self.budget = self.actual_budget

        super().save(*args, **kwargs)


class Department(models.Model):
    PROJECT_MANAGEMENT = 'PROJECT_MANAGEMENT'
    MECHANICAL_DESIGN = 'MECHANICAL_DESIGN'
    ELECTRICAL_DESIGN = 'ELECTRICAL_DESIGN'
    IN_HOUSE_COMMISSIONING = 'IN_HOUSE_COMMISSIONING'
    MECHANICAL_INSTALLATION = 'MECHANICAL_INSTALLATION'
    ELECTRICAL_INSTALLATION = 'ELECTRICAL_INSTALLATION'
    ON_SITE_COMMISSIONING = 'ON_SITE_COMMISSIONING'
    SUPPORT_FUNCTION = 'SUPPORT_FUNCTION'

    DEPARTMENT_CHOICES = [
        (PROJECT_MANAGEMENT, 'Project Management'),
        (MECHANICAL_DESIGN, 'Mechanical Design'),
        (ELECTRICAL_DESIGN, 'Electrical Design'),
        (IN_HOUSE_COMMISSIONING, 'In-House Commissioning'),
        (MECHANICAL_INSTALLATION, 'Mechanical Installation'),
        (ELECTRICAL_INSTALLATION, 'Electrical Installation'),
        (ON_SITE_COMMISSIONING, 'On-Site Commissioning'),
        (SUPPORT_FUNCTION, 'Support Function'),
    ]

    project = models.ForeignKey(Project,on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.00)], help_text="Hourly rate for this department (project-specific)")

    # Planned values (can be updated manually or via import)
    budget_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0.00)], help_text="Budgeted hours for this department")
    budget_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0.00)], help_text="Budgeted cost (hours * rate)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['project', 'name']]
        ordering = ['name']
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return f"{self.get_name_display()} ({self.project.co_no})"


class SubDepartment(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='sub_departments')
    code = models.CharField(max_length=50)
    role_descrptn = models.CharField(max_length=255, null=True, blank=True)
    inkrement = models.CharField(max_length=255, null=True, blank=True)

    # Baseline (original budget from project creation - never changes)
    baseline_budget_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0.00)])
    baseline_budget_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0.00)])

    # Current/Actual (updated via budget APIs)
    budget_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0.00)])

    budget_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0.00)])

    forecast_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True)
    forecast_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, blank=True)
    forecast_override = models.BooleanField(default=False)

    forecast_overridden_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='forecast_overrides')
    forecast_overridden_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['department', 'code']]
        ordering = ['code']
        verbose_name = "Sub-Department"
        verbose_name_plural = "Sub-Departments"

    # def save(self, *args, **kwargs):
    #     if self.forecast_override:
    #         dept = self.department
    #         project = dept.project
    #         self.forecast_cost = self.forecast_hours * dept.hourly_rate * project.exchange_rate
    #     super().save(*args, **kwargs)


    def save(self, *args, **kwargs):
        dept = self.department
        project = dept.project
        rate_inr = dept.hourly_rate * project.exchange_rate

        # Sync budget_cost ↔ budget_hours
        if self.budget_cost and rate_inr > 0:
            self.budget_hours = self.budget_cost / rate_inr
        elif self.budget_hours is not None:
            self.budget_cost = self.budget_hours * rate_inr

        # Forecast override
        if self.forecast_override:
            self.forecast_cost = self.forecast_hours * rate_inr

        super().save(*args, **kwargs)

    def current_forecast_hours_display(self):
        if self.forecast_override:
            return f"Manual: {self.forecast_hours} hours"
        else:
            return "Auto: Budget - Actual (calculated in snapshot)"
    current_forecast_hours_display.short_description = "Current Forecast Hours"

    def current_forecast_cost_display(self):
        if self.forecast_override:
            return f"₹{self.forecast_cost:,.2f}"
        else:
            return "Auto-calculated in snapshot"
    current_forecast_cost_display.short_description = "Current Forecast Cost (INR)"

    def __str__(self):
        return f"{self.code}: {self.role_descrptn} ({self.department})"


class CostCategory(models.Model):
    KTFT = 'KTFT'
    KTES = 'KTES'
    KTEP = 'KTEP'
    KTMA = 'KTMA'
    KTHP = 'KTHP'
    ZKE = 'ZKE'
    F_V = 'F+V'
    SOKO = 'SOKO'
    RK = 'RK'
    AS = 'ASSEMBLY SERVICES'
    DS = 'DESIGN SERVICES'
    ST = 'STATIONARY'
    QUAL_CHECK = 'QUALITY CHECKING'
    FEC = 'FACTORY EQUIPMENTS CONSUMABLES'

    COST_CATEGORY_CHOICES = [
        (KTFT, 'KTFT Manufacturing parts'),
        (KTES, 'KTES Electrical parts (cabinet)'),
        (KTEP, 'KTEP Electrical parts (periphery)'),
        (KTMA, 'KTMA Mechanical parts'),
        (KTHP, 'KTHP Pneumatic parts'),
        (ZKE, 'ZKE Purchase units'),
        (F_V, 'F_V Packing & Transport'),
        (SOKO, 'SOKO Special costs'),
        (RK, 'RK Travel costs'),
        (AS, 'ASSEMBLY SERVICES'),
        (DS, 'DESIGN SERVICE'),
        (ST, 'STATIONARY'),
        (QUAL_CHECK, 'QC (QUALITY CHECKING SERVICES)'),
        (FEC, 'FACTORY EQUIPMENTS CONSUMABLES'),
    ]

    code = models.CharField(max_length=200, choices=COST_CATEGORY_CHOICES, unique=True)
    name = models.CharField(max_length=255, editable=False)

    mat_code = models.CharField(max_length=255, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.name = dict(self.COST_CATEGORY_CHOICES).get(self.code, self.code)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code}: {self.get_code_display()} ({self.mat_code})"

    class Meta:
        verbose_name = "Cost Category"
        verbose_name_plural = "Cost Categories"
        ordering = ['code']


class ProjectCostCategory(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='project_cost_categories')
    cost_category = models.ForeignKey(CostCategory, on_delete=models.PROTECT)
    
    # Baseline (original budget from project creation)
    baseline_budget_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0.00)])

    # Current/Actual (updated via budget APIs)
    budget_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0.00)])

    forecast_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, blank=True)
    forecast_override = models.BooleanField(default=False)

    # In ProjectCostCategory model — add this field
    actual_override = models.BooleanField(default=False, help_text="If true, use manual actuals for RK instead of PO")

    forecast_overridden_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='material_forecast_overrides')
    forecast_overridden_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['project', 'cost_category']]
        ordering = ['cost_category__code']
        verbose_name = "Project Cost Category"
        verbose_name_plural = "Project Cost Categories"

    def __str__(self):
        return f"{self.cost_category.code} for {self.project.co_no}"


class TimesheetEntry(models.Model):
    date = models.DateField(db_index=True)
    emp_cd = models.CharField(max_length=20, db_index=True)
    emp_name = models.CharField(max_length=100)
    role_description = models.CharField(max_length=255)
    co_no = models.CharField(max_length=20, db_index=True)
    hours = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])

    imported_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Timesheet Entry (Raw)"
        verbose_name_plural = "Timesheet Entries (Raw)"
        indexes = [
            models.Index(fields=['date', 'emp_cd']),
            models.Index(fields=['co_no']),
            models.Index(fields=['date', 'co_no']),
            models.Index(fields=['date', 'emp_cd', 'co_no', 'role_description']),  # For performance
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['date', 'emp_cd', 'co_no', 'role_description'],
                name='unique_timesheet_entry'
            )
        ]

    def __str__(self):
        return f"{self.date} | {self.emp_cd} {self.emp_name} | {self.co_no} | {self.role_description} | {self.hours}h"

    @property
    def project_code(self) -> str:
        return self.co_no[:5] if self.co_no and len(self.co_no) >= 5 else ""


class POData(models.Model):
    # Critical fields (must be imported)
    co_no = models.CharField(max_length=20, db_index=True, help_text="CONo")
    mat_code = models.CharField(max_length=100, db_index=True, help_text="MatCode")
    po_value_inr = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(0)])

    # Highly useful additional fields from the dump
    po_no = models.CharField(max_length=50, blank=True, help_text="PoNo")
    po_date = models.DateField(null=True, blank=True, help_text="Po.Date")
    sr_no = models.PositiveIntegerField(null=True, blank=True, help_text="SrNo")
    item_code = models.CharField(max_length=100, blank=True, help_text="ItemCode")
    description = models.TextField(blank=True, help_text="Description")
    supplier_name = models.CharField(max_length=255, blank=True, help_text="SupplierName")
    project_name = models.CharField(max_length=255, blank=True, help_text="ProjName")

    imported_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "PO Data Entry (Raw)"
        verbose_name_plural = "PO Data Entries (Raw)"
        indexes = [
            models.Index(fields=['co_no']),
            models.Index(fields=['mat_code']),
            models.Index(fields=['co_no', 'mat_code']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['co_no', 'po_no', 'sr_no'],
                name='unique_po_line'
            )
        ]

    def __str__(self):
        return f"{self.co_no} | {self.po_no or 'N/A'}:{self.sr_no or ''} | {self.mat_code} | ₹{self.po_value_inr:,}"

    @property
    def project_code(self) -> str:
        return self.co_no[:5] if self.co_no and len(self.co_no) >= 5 else ""

    @property
    def project_code(self) -> str:
        return self.co_no[:5] if self.co_no and len(self.co_no) >= 5 else ""


class PSRSnapshot(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='psr_snapshots')
    
    snapshot_date = models.DateField()
    
    frequency = models.CharField(
        max_length=20,
        choices=[
            ('MONTHLY', 'Monthly'),
            ('BIWEEKLY', 'Bi-weekly'),
            ('WEEKLY', 'Weekly'),
        ],
        default='MONTHLY'
    )
    
    data = models.JSONField(default=dict)

    # === LABOR (TIMESHEET) TOTALS ===
    labor_actual_hours = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    labor_budget_hours = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    labor_forecast_hours = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    labor_prognosis_hours = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    labor_actual_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    labor_budget_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    labor_forecast_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    labor_prognosis_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # === MATERIAL (COST TO GO) TOTALS ===
    material_actual_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    material_budget_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    material_forecast_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    material_prognosis_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    

    eff_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ter_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sum_prognosis = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    margin = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    factor = models.DecimalField(max_digits=8, decimal_places=3, default=0.0000)

    # === COMBINED TOTALS (kept for backward compatibility) ===
    total_actual_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)      # labor + material actual
    total_budget_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)      # labor + material budget
    total_forecast_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)    # labor + material forecast
    total_prognosis_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # labor + material prognosis
    
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = [['project', 'snapshot_date']]
        ordering = ['-snapshot_date']
        verbose_name = "PSR Snapshot"
        verbose_name_plural = "PSR Snapshots"

    def __str__(self):
        return f"PSR Snapshot {self.snapshot_date} - {self.project.co_no}"



#----------------------#
# Hours Update Section #
#----------------------#


class SubDepartmentBudgetAdjustment(models.Model):
    sub_department = models.ForeignKey('SubDepartment', on_delete=models.CASCADE, related_name='budget_adjustments')
    adjustment_date = models.DateTimeField(auto_now_add=True)
    adjusted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    
    note = models.TextField(help_text="Reason for budget hours adjustment")
    
    previous_budget_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    new_budget_hours = models.DecimalField(max_digits=12, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-adjustment_date']
        verbose_name = "Sub-Department Budget Adjustment"
        verbose_name_plural = "Sub-Department Budget Adjustments"

    def __str__(self):
        return f"Budget adj {self.adjustment_date.date()} - {self.sub_department} - {self.new_budget_hours}h"





class ProjectCostCategoryBudgetAdjustment(models.Model):
    project_cost_category = models.ForeignKey(
        ProjectCostCategory,
        on_delete=models.CASCADE,
        related_name='budget_adjustments'
    )
    adjustment_date = models.DateTimeField(auto_now_add=True)
    adjusted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    
    note = models.TextField(help_text="Reason for budget cost adjustment")
    
    previous_budget_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    new_budget_cost = models.DecimalField(max_digits=15, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-adjustment_date']
        verbose_name = "Project Cost Category Budget Adjustment"
        verbose_name_plural = "Project Cost Category Budget Adjustments"

    def __str__(self):
        return f"Budget adj {self.adjustment_date.date()} - {self.project_cost_category} - ₹{self.new_budget_cost:,}"



#---------------------------------#
# Hours Forecast Override Section #
#---------------------------------#

class ForecastAdjustment(models.Model):
    sub_department = models.ForeignKey(SubDepartment, on_delete=models.CASCADE, related_name='forecast_adjustments')
    adjustment_date = models.DateTimeField(auto_now_add=True)
    adjusted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    
    note = models.TextField(help_text="Overall reason for forecast adjustment")
    
    new_forecast_hours = models.DecimalField(max_digits=12, decimal_places=2)
    previous_forecast_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Adjustment on {self.adjustment_date.date()} by {self.adjusted_by} - {self.new_forecast_hours}h"


class ForecastAdjustmentLine(models.Model):
    adjustment = models.ForeignKey(ForecastAdjustment, on_delete=models.CASCADE, related_name='lines')
    description = models.CharField(max_length=255)
    hours = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    
    def __str__(self):
        return f"{self.description}: {self.hours}h"






#--------------------------------------#
# Cost To Go Forecast Override Section #
#--------------------------------------#


class MaterialForecastAdjustment(models.Model):
    project_cost_category = models.ForeignKey(ProjectCostCategory, on_delete=models.CASCADE, related_name='forecast_adjustments')
    adjustment_date = models.DateTimeField(auto_now_add=True)
    adjusted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    
    note = models.TextField(help_text="Reason for material forecast adjustment")
    
    previous_forecast_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    new_forecast_cost = models.DecimalField(max_digits=15, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Material Adj {self.adjustment_date.date()} - {self.project_cost_category} - ₹{self.new_forecast_cost:,}"


class MaterialForecastAdjustmentLine(models.Model):
    adjustment = models.ForeignKey(MaterialForecastAdjustment, on_delete=models.CASCADE, related_name='lines')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
    
    def __str__(self):
        return f"{self.description}: ₹{self.amount:,}"




class RKActualAdjustment(models.Model):
    project_cost_category = models.ForeignKey(
        'ProjectCostCategory',
        on_delete=models.CASCADE,
        related_name='rk_actual_adjustments',
        limit_choices_to={'cost_category__code': 'RK'}  # Only RK
    )
    adjusted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField(help_text="Reason for entering manual actuals")
    adjusted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RK Actual Adjustment - {self.project_cost_category.project.co_no} - {self.adjusted_at.date()}"

    class Meta:
        ordering = ['-adjusted_at']
        verbose_name = "RK Actual Adjustment"
        verbose_name_plural = "RK Actual Adjustments"


class RKActualAdjustmentLine(models.Model):
    adjustment = models.ForeignKey(RKActualAdjustment, on_delete=models.CASCADE, related_name='lines')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    def __str__(self):
        return f"{self.description} - ₹{self.amount}"

    class Meta:
        verbose_name = "RK Actual Line"
        verbose_name_plural = "RK Actual Lines"