# core/management/commands/generate_psr_snapshot.py

import datetime
from calendar import monthrange
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import (
    Project, TimesheetEntry, POData, Department, SubDepartment,
    ProjectCostCategory, CostCategory, PSRSnapshot
)


class Command(BaseCommand):
    help = "Generate PSR snapshot for a project up to a specific date (all costs in INR)"

    def add_arguments(self, parser):
        parser.add_argument('co_no', type=str, help="Project co_no")
        parser.add_argument('--date', type=str, required=True, help="Snapshot end date (YYYY-MM-DD)")
        parser.add_argument('--frequency', type=str, default='MONTHLY', choices=['MONTHLY', 'BIWEEKLY', 'WEEKLY'])

    def handle(self, *args, **options):
        co_no = options['co_no']
        snapshot_date_str = options['date']
        frequency = options['frequency']

        try:
            snapshot_date = datetime.datetime.strptime(snapshot_date_str, '%Y-%m-%d').date()
        except ValueError:
            self.stderr.write(self.style.ERROR("Invalid date format. Use YYYY-MM-DD"))
            return

        project = Project.objects.filter(co_no=co_no).first()
        if not project:
            self.stderr.write(self.style.ERROR(f"Project {co_no} not found"))
            return

        self.stdout.write(self.style.SUCCESS(f"Generating snapshot for {project} on {snapshot_date}"))

        # project_prefix = co_no[:5]
        exchange_rate = project.exchange_rate

        # Calculate last month end date
        first_day_current = snapshot_date.replace(day=1)
        last_day_prev_month = first_day_current - datetime.timedelta(days=1)
        last_month_date = last_day_prev_month.replace(day=monthrange(last_day_prev_month.year, last_day_prev_month.month)[1])

        previous_snapshot = PSRSnapshot.objects.filter(
            project=project,
            snapshot_date=last_month_date
        ).first()

        data = {"TIMESHEET": {"HOURS": {}, "COST": {}}, "COST TO GO": {"COST": {}}}

        # Separate totals
        labor_actual_hours = Decimal('0')
        labor_budget_hours = Decimal('0')
        labor_forecast_hours = Decimal('0')
        labor_prognosis_hours = Decimal('0')

        labor_actual_cost = Decimal('0')
        labor_budget_cost = Decimal('0')
        labor_forecast_cost = Decimal('0')
        labor_prognosis_cost = Decimal('0')

        material_actual_cost = Decimal('0')
        material_budget_cost = Decimal('0')
        material_forecast_cost = Decimal('0')
        material_prognosis_cost = Decimal('0')

        # ================================
        # Labor Processing
        # ================================
        timesheet_entries = TimesheetEntry.objects.filter(
            co_no__startswith=project.co_no,
            date__lte=snapshot_date
        )

        labor_actuals = {}
        for entry in timesheet_entries:
            # sub_dept = SubDepartment.objects.filter(
            #     role_descrptn__iexact=entry.role_description.strip()
            # ).first()

            # Walkthrough 1

            sub_dept = SubDepartment.objects.filter(
                department__project=project,
                role_descrptn__iexact=entry.role_description.strip()
            ).order_by('id').first()

            if sub_dept:
                dept = sub_dept.department
                hours = Decimal(str(entry.hours))
                cost_inr = hours * dept.hourly_rate * exchange_rate

                labor_actuals.setdefault(sub_dept.id, {'hours': Decimal('0'), 'cost_inr': Decimal('0')})
                labor_actuals[sub_dept.id]['hours'] += hours
                labor_actuals[sub_dept.id]['cost_inr'] += cost_inr

        for dept in project.departments.all():
            dept_name = dept.name
            data["TIMESHEET"]["HOURS"][dept_name] = {}
            data["TIMESHEET"]["COST"][dept_name] = {}

            for sub_dept in dept.sub_departments.all():
                sub_code = sub_dept.code
                sub_dept_id = sub_dept.id
                inkrement = sub_dept.inkrement or ""

                act = labor_actuals.get(sub_dept.id, {'hours': Decimal('0'), 'cost_inr': Decimal('0')})
                actual_hours = act['hours']
                actual_cost_inr = act['cost_inr']

                # current_budget_hours = sub_dept.budget_hours
                # current_budget_cost_inr = current_budget_hours * dept.hourly_rate * exchange_rate

                # === NEW: Use budget_cost as primary, calculate hours from it ===
                current_budget_cost_inr = sub_dept.budget_cost
                rate_inr = dept.hourly_rate * exchange_rate
                current_budget_hours = current_budget_cost_inr / rate_inr if rate_inr > 0 else Decimal('0')

                baseline_budget_hours = sub_dept.baseline_budget_hours
                baseline_budget_cost_inr = baseline_budget_hours * dept.hourly_rate * exchange_rate

                # Forecast
                if sub_dept.forecast_override:
                    forecast_hours = sub_dept.forecast_hours
                    forecast_cost_inr = sub_dept.forecast_cost
                else:
                    forecast_hours = max(current_budget_hours - actual_hours, Decimal('0'))
                    forecast_cost_inr = max(current_budget_cost_inr - actual_cost_inr, Decimal('0'))

                prognosis_hours = actual_hours + forecast_hours
                prognosis_cost_inr = actual_cost_inr + forecast_cost_inr

                # Last month actuals
                last_month_actual_hours = Decimal('0')
                last_month_actual_cost = Decimal('0')
                if previous_snapshot and previous_snapshot.data:
                    prev_cost = previous_snapshot.data.get("TIMESHEET", {}).get("COST", {}).get(dept_name, {}).get(sub_code, {})
                    last_month_actual_cost = Decimal(str(prev_cost.get("actuals", 0.0)))
                    rate_inr = dept.hourly_rate * exchange_rate
                    last_month_actual_hours = last_month_actual_cost / rate_inr if rate_inr > 0 else Decimal('0')

                # Rounded percentages
                balance_pct = round(float((current_budget_cost_inr / prognosis_cost_inr * 100) if prognosis_cost_inr else 0), 2)
                rest_pct = round(float((prognosis_cost_inr / actual_cost_inr * 100) if actual_cost_inr else 0), 2)

                # TIMESHEET HOURS
                data["TIMESHEET"]["HOURS"][dept_name][sub_code] = {
                    "id": sub_dept_id,
                    "inkrement": inkrement,
                    "baseline_budget": float(baseline_budget_hours),
                    "last_month_actuals": float(last_month_actual_hours),
                    "actuals": float(actual_hours),
                    "budget": float(current_budget_hours),
                    "forecast": float(forecast_hours),
                    "prognosis": float(prognosis_hours),
                    "balance": float(current_budget_hours - prognosis_hours),
                    "balance_percentage": balance_pct,
                    "rest": float(forecast_hours),
                    "rest_percentage": rest_pct,
                }

                # TIMESHEET COST
                data["TIMESHEET"]["COST"][dept_name][sub_code] = {
                    "id": sub_dept_id,
                    "inkrement": inkrement,
                    "baseline_budget": float(baseline_budget_cost_inr),
                    "baseline_budget": float(sub_dept.baseline_budget_cost),
                    "last_month_actuals": float(last_month_actual_cost),
                    "actuals": float(actual_cost_inr),
                    "budget": float(current_budget_cost_inr),
                    "forecast": float(forecast_cost_inr),
                    "prognosis": float(prognosis_cost_inr),
                    "balance": float(current_budget_cost_inr - prognosis_cost_inr),
                    "balance_percentage": balance_pct,
                    "rest": float(forecast_cost_inr),
                    "rest_percentage": rest_pct,
                }

                # Accumulate labor totals
                labor_actual_hours += actual_hours
                labor_budget_hours += current_budget_hours
                labor_forecast_hours += forecast_hours
                labor_prognosis_hours += prognosis_hours

                labor_actual_cost += actual_cost_inr
                # labor_budget_cost += current_budget_cost_inr
                labor_budget_cost += sub_dept.budget_cost
                labor_forecast_cost += forecast_cost_inr
                labor_prognosis_cost += prognosis_cost_inr

        # ================================
        # Material Processing
        # ================================
        po_entries = POData.objects.filter(co_no__startswith=project.co_no)
        material_actuals = {}
        for entry in po_entries:
            cat = CostCategory.objects.filter(mat_code__iexact=entry.mat_code.strip()).first()
            if cat:
                cost_inr = Decimal(str(entry.po_value_inr))
                material_actuals[cat.code] = material_actuals.get(cat.code, Decimal('0')) + cost_inr
                # ← Removed: and cat.code != 'RK' — now includes RK

        for cat in CostCategory.objects.all():
            cat_code = cat.code
            pcc = project.project_cost_categories.filter(cost_category=cat).first()
            if not pcc:
                continue

            pcc_id = pcc.id
            inkrement = cat.get_code_display()

            current_budget_inr = pcc.budget_cost
            baseline_budget_inr = pcc.baseline_budget_cost

            # Determine actuals — RK override logic
            if cat_code == 'RK' and pcc.actual_override:
                rk_actual = sum(
                    line.amount for adj in pcc.rk_actual_adjustments.all()
                    for line in adj.lines.all()
                )
                actual_inr = Decimal(rk_actual)
            else:
                actual_inr = material_actuals.get(cat_code, Decimal('0'))

            # Forecast
            if pcc.forecast_override:
                forecast_inr = pcc.forecast_cost
            else:
                forecast_inr = max(current_budget_inr - actual_inr, Decimal('0'))

            prognosis_inr = actual_inr + forecast_inr

            last_month_actual_inr = Decimal('0')
            if previous_snapshot and previous_snapshot.data:
                prev = previous_snapshot.data.get("COST TO GO", {}).get("COST", {}).get(cat_code, {})
                last_month_actual_inr = Decimal(str(prev.get("actuals", 0.0)))

            balance_pct = round(float((current_budget_inr / prognosis_inr * 100) if prognosis_inr else 0), 2)
            rest_pct = round(float((prognosis_inr / actual_inr * 100) if actual_inr else 0), 2)

            data["COST TO GO"]["COST"][cat_code] = {
                "id": pcc_id,
                "inkrement": inkrement,
                "baseline_budget": float(baseline_budget_inr),
                "last_month_actuals": float(last_month_actual_inr),
                "actuals": float(actual_inr),
                "budget": float(current_budget_inr),
                "forecast": float(forecast_inr),
                "prognosis": float(prognosis_inr),
                "balance": float(current_budget_inr - prognosis_inr),
                "balance_percentage": balance_pct,
                "rest": float(forecast_inr),
                "rest_percentage": rest_pct,
            }

            # Accumulate material totals
            material_actual_cost += actual_inr
            material_budget_cost += current_budget_inr
            material_forecast_cost += forecast_inr
            material_prognosis_cost += prognosis_inr
        
        
        

        # ================================
        # New KPI Calculations (with First Snapshot Support)
        # ================================
        # Determine if this is the first snapshot (no actuals yet)
        
        # Delete this part later
        # labor_actual_cost = 0 
        # material_actual_cost = 0
        # Delete this part later
        
        is_first_snapshot = (labor_actual_cost == 0 and material_actual_cost == 0)

        if is_first_snapshot:
            # Use pre-calculated values from Project model (financial plan)
            total_budget_cost = project.budget  # = Actual Budget (HK - TER - EFF)
            eff_value = project.eff_value
            ter_value = project.ter_value
            sum_prognosis = project.budget + eff_value + ter_value
            margin = project.sales_value - sum_prognosis
            factor = project.factor
            total_actual_cost = Decimal('0')
            total_forecast_cost = sum_prognosis  # Same as prognosis in initial state
            total_prognosis_cost = sum_prognosis
        else:
            # Normal ongoing snapshot
            prognosis_hours_po = labor_prognosis_cost + material_prognosis_cost

            eff_value = project.eff_value  # Still from project (percentages fixed)
            ter_value = project.ter_value

            sum_prognosis = prognosis_hours_po + eff_value + ter_value
            margin = project.sales_value - sum_prognosis
            factor = project.sales_value / sum_prognosis if sum_prognosis > 0 else Decimal('0')
            
            total_actual_cost = labor_actual_cost + material_actual_cost
            total_budget_cost = labor_budget_cost + material_budget_cost
            total_forecast_cost = labor_forecast_cost + material_forecast_cost
            total_prognosis_cost = sum_prognosis

        # Save snapshot with all fields
        snapshot, created = PSRSnapshot.objects.update_or_create(
            project=project,
            snapshot_date=snapshot_date,
            defaults={
                'frequency': frequency,
                'data': data,

                # Labor
                'labor_actual_hours': labor_actual_hours,
                'labor_budget_hours': labor_budget_hours,
                'labor_forecast_hours': labor_forecast_hours,
                'labor_prognosis_hours': labor_prognosis_hours,
                'labor_actual_cost': labor_actual_cost,
                'labor_budget_cost': labor_budget_cost,
                'labor_forecast_cost': labor_forecast_cost,
                'labor_prognosis_cost': labor_prognosis_cost,

                # Material
                'material_actual_cost': material_actual_cost,
                'material_budget_cost': material_budget_cost,
                'material_forecast_cost': material_forecast_cost,
                'material_prognosis_cost': material_prognosis_cost,

                # New KPI fields
                'eff_value': eff_value,
                'ter_value': ter_value,
                'sum_prognosis': sum_prognosis,
                'margin': margin,
                'factor': factor,

                # Combined
                'total_actual_cost': total_actual_cost,
                'total_budget_cost': total_budget_cost,
                'total_forecast_cost': total_forecast_cost,
                'total_prognosis_cost': total_prognosis_cost,
            }
        )
        # self.stdout.write("\n=== PSR SNAPSHOT TOTALS ===")
        # self.stdout.write(f"Labor Actual Hours      : {labor_actual_hours:,.2f}")
        # self.stdout.write(f"Labor Budget Hours      : {labor_budget_hours:,.2f}")
        # self.stdout.write(f"Labor Forecast Hours    : {labor_forecast_hours:,.2f}")
        # self.stdout.write(f"Labor Prognosis Hours   : {labor_prognosis_hours:,.2f}")
        # self.stdout.write("")
        # self.stdout.write(f"Labor Actual Cost (INR) : ₹{labor_actual_cost:,.2f}")
        # self.stdout.write(f"Labor Budget Cost (INR) : ₹{labor_budget_cost:,.2f}")
        # self.stdout.write(f"Labor Forecast Cost     : ₹{labor_forecast_cost:,.2f}")
        # self.stdout.write(f"Labor Prognosis Cost    : ₹{labor_prognosis_cost:,.2f}")
        # self.stdout.write("")
        # self.stdout.write(f"Material Actual Cost    : ₹{material_actual_cost:,.2f}")
        # self.stdout.write(f"Material Budget Cost    : ₹{material_budget_cost:,.2f}")
        # self.stdout.write(f"Material Forecast Cost  : ₹{material_forecast_cost:,.2f}")
        # self.stdout.write(f"Material Prognosis Cost : ₹{material_prognosis_cost:,.2f}")
        # self.stdout.write("")
        # self.stdout.write(f"EFF Value (INR)         : ₹{eff_value:,.2f}")
        # self.stdout.write(f"TER Value (INR)         : ₹{ter_value:,.2f}")
        # self.stdout.write("")
        # self.stdout.write(f"Sum Prognosis (INR)     : ₹{sum_prognosis:,.2f}")
        # self.stdout.write(f"Margin (INR)            : ₹{margin:,.2f}")
        # self.stdout.write(f"Factor                  : {factor:.3f}")
        # self.stdout.write("")
        # self.stdout.write(f"Total Actual Cost       : ₹{total_actual_cost:,.2f}")
        # self.stdout.write(f"Total Budget Cost       : ₹{total_budget_cost:,.2f}")
        # self.stdout.write(f"Total Forecast Cost     : ₹{total_forecast_cost:,.2f}")
        # self.stdout.write(f"Total Prognosis Cost    : ₹{total_prognosis_cost:,.2f}")
        # self.stdout.write("==========================\n")
        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Snapshot {action} successfully for {project.co_no} on {snapshot_date}"))