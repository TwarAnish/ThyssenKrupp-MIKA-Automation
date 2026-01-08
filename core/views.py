# core/views.py
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.generics import CreateAPIView
from django.core.management import call_command
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from collections import defaultdict
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from django.db.models import Max
from django.db.models import Q
from datetime import datetime
from decimal import Decimal
from io import StringIO


from .serializers import (PSRSnapshotSerializer, 
                          SubDepartmentBudgetSerializer, 
                          SubDepartmentForecastOverrideSerializer,
                          ProjectCreateSerializer,
                          ProjectBasicSerializer,
                          ProjectUpdateSerializer,
                          PSRSnapshotKPISerializer,
                          ProjectLatestSnapshotSerializer, 
                          MonthlyCumulativeKPISerializer,
                          RKActualAdjustmentSerializer)

from .models import (Project, 
                     PSRSnapshot,
                     Department, SubDepartment, 
                     CostCategory, ProjectCostCategory, 
                     SubDepartmentBudgetAdjustment, ProjectCostCategoryBudgetAdjustment,
                     ForecastAdjustment, ForecastAdjustmentLine, 
                     MaterialForecastAdjustment, MaterialForecastAdjustmentLine,
                     RKActualAdjustment, RKActualAdjustmentLine,)


class ProjectPSRSnapshotTimesheetView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, co_no, snapshot_date=None):
        project = get_object_or_404(Project, co_no=co_no)

        if snapshot_date:
            snapshot = get_object_or_404(PSRSnapshot, project=project, snapshot_date=snapshot_date)
        else:
            snapshot = PSRSnapshot.objects.filter(project=project).order_by('-snapshot_date').first()
            if not snapshot:
                return Response({"error": "No snapshots available for this project"}, status=status.HTTP_404_NOT_FOUND)

        timesheet_data = snapshot.data.get("TIMESHEET", {"HOURS": {}, "COST": {}})

        # List of keys that are percentages (keep 2 decimals)
        PERCENTAGE_KEYS = {
            'balance_percentage',
            'rest_percentage',
            # Add any future percentage keys here
        }

        def round_value(value, key=None):
            if isinstance(value, float):
                if key in PERCENTAGE_KEYS:
                    return round(value, 2)
                else:
                    return round(value, 1)
            return value

        def round_nested(obj):
            if isinstance(obj, dict):
                return {k: round_nested(v) if k not in PERCENTAGE_KEYS else round_value(v, k) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [round_nested(item) for item in obj]
            elif isinstance(obj, float):
                return round_value(obj)
            else:
                return obj

        # Apply rounding to entire TIMESHEET structure
        rounded_timesheet = {
            section: {
                dept: {
                    sub_code: round_nested(values)
                    for sub_code, values in sub_depts.items()
                }
                for dept, sub_depts in timesheet_data.get(section, {}).items()
            }
            for section in ["HOURS", "COST"]
        }

        return Response({
            "project": project.co_no,
            "snapshot_date": snapshot.snapshot_date,
            "timesheet": rounded_timesheet
        }, status=status.HTTP_200_OK)



class ProjectPSRSnapshotCostToGoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, co_no, snapshot_date=None):
        project = get_object_or_404(Project, co_no=co_no)

        if snapshot_date:
            snapshot = get_object_or_404(PSRSnapshot, project=project, snapshot_date=snapshot_date)
        else:
            snapshot = PSRSnapshot.objects.filter(project=project).order_by('-snapshot_date').first()
            if not snapshot:
                return Response({"error": "No snapshots available for this project"}, status=status.HTTP_404_NOT_FOUND)

        # Return only COST TO GO data
        cost_to_go_data = snapshot.data.get("COST TO GO", {"COST": {}})

        return Response({
            "project": project.co_no,
            "snapshot_date": snapshot.snapshot_date,
            "cost_to_go": cost_to_go_data
        }, status=status.HTTP_200_OK)




class ProjectSnapshotTimesheetHistoryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, co_no):
        project = get_object_or_404(Project, co_no=co_no)

        snapshots = PSRSnapshot.objects.filter(project=project).order_by('snapshot_date')

        if not snapshots.exists():
            return Response(
                {"detail": "No snapshots available for this project."},
                status=status.HTTP_404_NOT_FOUND
            )

        HOURS = []
        COST = []

        for snapshot in snapshots:
            month_year = snapshot.snapshot_date.strftime('%B %Y')

            # HOURS data
            HOURS.append({
                "month": month_year,
                "actual_hours": float(snapshot.labor_actual_hours),
                "budget_hours": float(snapshot.labor_budget_hours),
                "forecast_hours": float(snapshot.labor_forecast_hours),
                "prognosis_hours": float(snapshot.labor_prognosis_hours),
            })

            # COST data
            COST.append({
                "month": month_year,
                "actual_cost": float(snapshot.labor_actual_cost),
                "budget_cost": float(snapshot.labor_budget_cost),
                "forecast_cost": float(snapshot.labor_forecast_cost),
                "prognosis_cost": float(snapshot.labor_prognosis_cost),
            })

        return Response({
            "project": project.co_no,
            "project_name": project.project_name,
            "HOURS": HOURS,
            "COST": COST
        })


class ProjectSnapshotCostToGoHistoryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, co_no):
        project = get_object_or_404(Project, co_no=co_no)

        snapshots = PSRSnapshot.objects.filter(project=project).order_by('snapshot_date')

        if not snapshots.exists():
            return Response({"detail": "No snapshots available for this project."}, status=status.HTTP_404_NOT_FOUND)

        history = []

        for snapshot in snapshots:
            # Format as "January 2025"
            month_year = snapshot.snapshot_date.strftime('%B %Y')
            
            month_data = {
                "month": month_year,
                "actual_cost": float(snapshot.material_actual_cost),
                "budget_cost": float(snapshot.material_budget_cost),
                "forecast_cost": float(snapshot.material_forecast_cost),
                "prognosis_cost": float(snapshot.material_prognosis_cost),
            }
            history.append(month_data)

        return Response({
            "project": project.co_no,
            "project_name": project.project_name,
            "cost_to_go_history": history
        })





class SubDepartmentBudgetUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    # permission_classes = [AllowAny]


    def patch(self, request, pk):
        sub_dept = get_object_or_404(SubDepartment, pk=pk)
        user = request.user

        new_hours = request.data.get('budget_hours')
        note = request.data.get('note')

        if new_hours is None:
            return Response({"detail": "budget_hours is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not note:
            return Response({"detail": "note (reason for change) is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_hours = Decimal(str(new_hours))
            if new_hours < 0:
                raise ValueError
        except:
            return Response({"detail": "budget_hours must be a valid positive number."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Save previous value for history
            previous_hours = sub_dept.budget_hours

            # Update current budget only (baseline remains unchanged)
            sub_dept.budget_hours = new_hours
            sub_dept.budget_cost = new_hours * sub_dept.department.hourly_rate * sub_dept.department.project.exchange_rate
            sub_dept.save()

            # Create adjustment record
            SubDepartmentBudgetAdjustment.objects.create(
                sub_department=sub_dept,
                adjusted_by=user,
                note=note,
                previous_budget_hours=previous_hours,
                new_budget_hours=new_hours
            )

        # Regenerate snapshot
        project = sub_dept.department.project
        latest_snapshot = project.psr_snapshots.order_by('-snapshot_date').first()
        if latest_snapshot:
            call_command(
                'generate_psr_snapshot',
                str(project.co_no),
                '--date',
                latest_snapshot.snapshot_date.strftime('%Y-%m-%d')
            )

        return Response({
            "detail": "Budget hours updated successfully with reason recorded.",
            "baseline_budget_hours": float(sub_dept.baseline_budget_hours),
            "current_budget_hours": float(new_hours),
            "snapshot_regenerated": latest_snapshot.snapshot_date.strftime('%Y-%m-%d') if latest_snapshot else None
        }, status=status.HTTP_200_OK)


class ProjectCostCategoryBudgetUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    # permission_classes = [AllowAny]

    def patch(self, request, pk):
        pcc = get_object_or_404(ProjectCostCategory, pk=pk)
        user = request.user

        new_cost = request.data.get('budget_cost')
        note = request.data.get('note')

        if new_cost is None:
            return Response({"detail": "budget_cost is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not note:
            return Response({"detail": "note (reason for change) is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_cost = Decimal(str(new_cost))
            if new_cost < 0:
                raise ValueError
        except:
            return Response({"detail": "budget_cost must be a valid positive number."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            previous_cost = pcc.budget_cost

            # Update current budget only (baseline remains unchanged)
            pcc.budget_cost = new_cost
            pcc.save()

            ProjectCostCategoryBudgetAdjustment.objects.create(
                project_cost_category=pcc,
                adjusted_by=user,
                note=note,
                previous_budget_cost=previous_cost,
                new_budget_cost=new_cost
            )

        # Regenerate snapshot
        project = pcc.project
        latest_snapshot = project.psr_snapshots.order_by('-snapshot_date').first()
        if latest_snapshot:
            call_command(
                'generate_psr_snapshot',
                str(project.co_no),
                '--date',
                latest_snapshot.snapshot_date.strftime('%Y-%m-%d')
            )

        return Response({
            "detail": "Budget cost updated successfully with reason recorded.",
            "baseline_budget_cost": float(pcc.baseline_budget_cost),
            "current_budget_cost": float(new_cost),
            "snapshot_regenerated": latest_snapshot.snapshot_date.strftime('%Y-%m-%d') if latest_snapshot else None
        }, status=status.HTTP_200_OK)



class SubDepartmentForecastOverrideView(APIView):
    permission_classes = [IsAuthenticated]
    # permission_classes = [AllowAny]

    def patch(self, request, pk):
        sub_dept = get_object_or_404(SubDepartment, pk=pk)
        user = request.user

        note = request.data.get('note')
        lines_data = request.data.get('lines', [])

        if not note:
            return Response({"detail": "Note (reason) is required for forecast override."}, status=status.HTTP_400_BAD_REQUEST)

        if not lines_data or not isinstance(lines_data, list):
            return Response({"detail": "Lines (list of description + hours) is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate total hours from lines
        total_hours = Decimal('0')
        for line in lines_data:
            hours = line.get('hours')
            if hours is None or Decimal(str(hours)) < 0:
                return Response({"detail": "Each line must have valid positive hours."}, status=status.HTTP_400_BAD_REQUEST)
            total_hours += Decimal(str(hours))

        if total_hours == 0:
            return Response({"detail": "Total forecast hours cannot be zero."}, status=status.HTTP_400_BAD_REQUEST)

        # Begin transaction for atomicity
        
        with transaction.atomic():
            # Save previous value for audit
            previous_forecast = sub_dept.forecast_hours

            # Update SubDepartment
            sub_dept.forecast_override = True
            sub_dept.forecast_hours = total_hours
            # Auto-calculate forecast_cost
            dept = sub_dept.department
            project = dept.project
            sub_dept.forecast_cost = total_hours * dept.hourly_rate * project.exchange_rate

            sub_dept.forecast_overridden_by = user
            sub_dept.forecast_overridden_at = timezone.now()
            sub_dept.save()

            # Create ForecastAdjustment record
            adjustment = ForecastAdjustment.objects.create(
                sub_department=sub_dept,
                adjusted_by=user,
                note=note,
                previous_forecast_hours=previous_forecast,
                new_forecast_hours=total_hours
            )

            # Create line items
            for line in lines_data:
                ForecastAdjustmentLine.objects.create(
                    adjustment=adjustment,
                    description=line['description'],
                    hours=Decimal(str(line['hours']))
                )

        # Regenerate latest snapshot
        project = sub_dept.department.project
        latest_snapshot = project.psr_snapshots.order_by('-snapshot_date').first()
        if latest_snapshot:
            latest_date = latest_snapshot.snapshot_date
            call_command(
                'generate_psr_snapshot',
                str(project.co_no),
                '--date',
                latest_date.strftime('%Y-%m-%d')
            )

        return Response({
            "detail": "Forecast override applied successfully with audit record.",
            "warning": "Manual forecast override is now active.",
            "total_forecast_hours": float(total_hours),
            "adjustment_id": adjustment.id,
            "snapshot_regenerated": latest_snapshot.snapshot_date.strftime('%Y-%m-%d') if latest_snapshot else None
        }, status=status.HTTP_200_OK)


class SubDepartmentGetForecastOverrideView(APIView):
    permission_classes = [IsAuthenticated]  # or AllowAny as needed

    def get(self, request, pk):
        sub_dept = get_object_or_404(SubDepartment, pk=pk)

        if not sub_dept.forecast_override:
            return Response({
                "forecast_override": False,
                "detail": "No manual forecast override is active. Using auto-calculated forecast (Budget - Actual)."
            }, status=status.HTTP_200_OK)

        # Use the correct field name — likely 'adjustment_date' or 'created_at'
        latest_adjustment = sub_dept.forecast_adjustments.order_by('-adjustment_date').first()
        # OR if it's auto_now_add on created_at:
        # latest_adjustment = sub_dept.forecast_adjustments.order_by('-created_at').first()

        if not latest_adjustment:
            return Response({
                "forecast_override": True,
                "detail": "Override flag is set but no adjustment record found.",
                "current_forecast_hours": float(sub_dept.forecast_hours),
                "current_forecast_cost": float(sub_dept.forecast_cost),
            }, status=status.HTTP_200_OK)

        lines = []
        for line in latest_adjustment.lines.all():
            lines.append({
                "description": line.description,
                "hours": float(line.hours)
            })

        return Response({
            "forecast_override": True,
            "current_forecast_hours": float(sub_dept.forecast_hours),
            "current_forecast_cost": float(sub_dept.forecast_cost),
            "adjustment": {
                "id": latest_adjustment.id,
                "note": latest_adjustment.note,
                "previous_forecast_hours": float(latest_adjustment.previous_forecast_hours),
                "new_forecast_hours": float(latest_adjustment.new_forecast_hours),
                "adjusted_by": latest_adjustment.adjusted_by.username if latest_adjustment.adjusted_by else None,
                "adjusted_at": latest_adjustment.adjustment_date.isoformat() if hasattr(latest_adjustment, 'adjustment_date') else latest_adjustment.created_at.isoformat(),
                "lines": lines
            }
        }, status=status.HTTP_200_OK)


class ProjectCostCategoryForecastOverrideView(APIView):
    permission_classes = [IsAuthenticated]
    # permission_classes = [AllowAny]

    def patch(self, request, pk):
        pcc = get_object_or_404(ProjectCostCategory, pk=pk)
        user = request.user

        note = request.data.get('note')
        lines_data = request.data.get('lines', [])

        if not note:
            return Response({"detail": "Note (reason) is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not lines_data or not isinstance(lines_data, list):
            return Response({"detail": "Lines list is required."}, status=status.HTTP_400_BAD_REQUEST)

        total_amount = Decimal('0')
        for line in lines_data:
            amount = line.get('amount')
            if amount is None or Decimal(str(amount)) <= 0:
                return Response({"detail": "Each line must have positive amount."}, status=status.HTTP_400_BAD_REQUEST)
            total_amount += Decimal(str(amount))

        if total_amount == 0:
            return Response({"detail": "Total forecast cost cannot be zero."}, status=status.HTTP_400_BAD_REQUEST)

        # Use transaction from top-level import (already in your imports)
        with transaction.atomic():
            previous_forecast = pcc.forecast_cost

            pcc.forecast_override = True
            pcc.forecast_cost = total_amount
            pcc.forecast_overridden_by = user
            pcc.forecast_overridden_at = timezone.now()  # ← This now works correctly
            pcc.save()

            adjustment = MaterialForecastAdjustment.objects.create(
                project_cost_category=pcc,
                adjusted_by=user,
                note=note,
                previous_forecast_cost=previous_forecast,
                new_forecast_cost=total_amount
            )

            for line in lines_data:
                MaterialForecastAdjustmentLine.objects.create(
                    adjustment=adjustment,
                    description=line['description'],
                    amount=Decimal(str(line['amount']))
                )

        # Regenerate snapshot
        project = pcc.project
        latest_snapshot = project.psr_snapshots.order_by('-snapshot_date').first()
        if latest_snapshot:
            call_command(
                'generate_psr_snapshot',
                str(project.co_no),
                '--date',
                latest_snapshot.snapshot_date.strftime('%Y-%m-%d')
            )

        return Response({
            "detail": "Material forecast override applied successfully.",
            "total_forecast_cost": float(total_amount),
            "adjustment_id": adjustment.id
        }, status=status.HTTP_200_OK)




# core/views.py

class ProjectCostCategoryGetForecastOverrideView(APIView):
    permission_classes = [IsAuthenticated]
    # permission_classes = [AllowAny]

    def get(self, request, pk):
        pcc = get_object_or_404(ProjectCostCategory, pk=pk)

        # Check if override is active
        if not pcc.forecast_override:
            return Response({
                "forecast_override": False,
                "detail": "No manual forecast override is active. Using auto-calculated forecast (Budget - Actual)."
            }, status=status.HTTP_200_OK)

        # ← CORRECT related_name: 'forecast_adjustments'
        latest_adjustment = pcc.forecast_adjustments.order_by('-adjustment_date').first()

        if not latest_adjustment:
            return Response({
                "forecast_override": True,
                "detail": "Override flag is set but no adjustment record found.",
                "current_forecast_cost": float(pcc.forecast_cost),
            }, status=status.HTTP_200_OK)

        # Serialize lines
        lines = []
        for line in latest_adjustment.lines.all():
            lines.append({
                "description": line.description,
                "amount": float(line.amount)
            })

        return Response({
            "forecast_override": True,
            "current_forecast_cost": float(pcc.forecast_cost),
            "adjustment": {
                "id": latest_adjustment.id,
                "note": latest_adjustment.note,
                "previous_forecast_cost": float(latest_adjustment.previous_forecast_cost),
                "new_forecast_cost": float(latest_adjustment.new_forecast_cost),
                "adjusted_by": latest_adjustment.adjusted_by.username if latest_adjustment.adjusted_by else None,
                "adjusted_at": latest_adjustment.adjustment_date.isoformat(),
                "lines": lines
            }
        }, status=status.HTTP_200_OK)





# Hardcoded SubDepartment details: code -> (role_descrptn, inkrement, department_name)
SUB_DEPT_DETAILS = {
    "PM": ("Project Management PRO", 
           "Project Manager", 
           "PROJECT_MANAGEMENT"),
    "POM": ("Site Manager BSTL", 
            "OnSide Manager", 
            "PROJECT_MANAGEMENT"),
    "PEM": ("Mechanical design coordinator MEC", 
            "Project Mechanical design Engineering Manager", 
            "MECHANICAL_DESIGN"),
    "KMA/KHP": ("Engineering Mechanical & Pneumatic Design KMA_KHP", 
                "Mechanical Design ", 
                "MECHANICAL_DESIGN"),
    "DET": ("Engineering Detailing DET", 
            "Detailing ", 
            "MECHANICAL_DESIGN"),
    "DOK": ("Documentation DOK_SERV", 
            "Documentation", 
            "MECHANICAL_DESIGN"),
    "SIM": ("Simulation", 
            "Simulation", 
            "MECHANICAL_DESIGN"),
    "2D": ("2D Detailing", 
           "2D Detailing", 
           "MECHANICAL_DESIGN"),
    "QC": ("Quality Checking", 
           "Quality Checking", 
           "MECHANICAL_DESIGN"),
    "PEC": ("Electrics coordinator-ELK ", 
            "Project Controls Engineering Manager", 
            "ELECTRICAL_DESIGN"),
    "KEL": ("Engineering Electrical Design KEL", 
            "Electrical Design", 
            "ELECTRICAL_DESIGN"),
    "KES": ("Electrical Design SPecial Software KES_KESs", 
            "Software  Design", 
            "IN_HOUSE_COMMISSIONING"),
    "IBS": ("Engineering Software & Commisioning Coordinator IBS", 
            "Software  Commissioning", 
            "IN_HOUSE_COMMISSIONING"),
    "IBSS": ("Commissioning & Special Software IBS_IBSs TKSY", 
             "Software  Commissioning", 
             "IN_HOUSE_COMMISSIONING"),
    "IBK": ("Engineering Software & Commissioning at customer site IBK_IBKs", 
            "Commissioning on site", 
            "ON_SITE_COMMISSIONING"),
    "PAM": ("", 
            "Manager Assembly & Installation", 
            "MECHANICAL_INSTALLATION"),
    "MMA/MHP": ("Mechanical,Pneumatic,Hydrauic Assembly on TKSY Shop Floor MMA_VMA_MHP", 
            "Mechanical Assembly", 
            "MECHANICAL_INSTALLATION"),
    "A+I(M)": ("Mechanical ,Pneumatic,Hydraulic Assembly On site AIM", 
            "Mechanical Assembly  on site", 
            "MECHANICAL_INSTALLATION"),
    "INS": ("Electrical Installation INS Inhouse", 
            "Electrical Installation", 
            "ELECTRICAL_INSTALLATION"),
    "A+I(E)": ("Electrical Installation on Site AIE", 
            "Electrical Installation  on site", 
            "ELECTRICAL_INSTALLATION"),
}


# core/views.py

class ProjectCreateView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProjectCreateSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        # Save project — this triggers save() override which calculates all derived fields
        project = serializer.save()

        # === Create Departments, SubDepartments, ProjectCostCategories ===
        dept_budgets = self.request.data.get('department_budgets', {})
        sub_budgets = self.request.data.get('sub_department_budgets', {})  # Now expects budget_cost
        cost_cat_budgets = self.request.data.get('cost_category_budgets', {})

        departments_map = {}

        # Create Departments
        for dept_code, dept_name in Department.DEPARTMENT_CHOICES:
            payload = dept_budgets.get(dept_code, {})
            hourly_rate = Decimal(str(payload.get('hourly_rate', '2000.00')))
            # budget_hours no longer used here — kept for reference
            # budget_hours = Decimal(str(payload.get('budget_hours', '0')))

            dept = Department.objects.create(
                project=project,
                name=dept_code,
                hourly_rate=hourly_rate,
                budget_hours=0,  # Will be updated via sub-department totals if needed
            )
            departments_map[dept_code] = dept

        for code, (role_descrptn, inkrement, dept_code) in SUB_DEPT_DETAILS.items():
            budget_cost_str = sub_budgets.get(code, '0')
            budget_cost = Decimal(str(budget_cost_str)) if budget_cost_str else Decimal('0')

            department = departments_map.get(dept_code)
            if not department:
                continue

            rate_inr = department.hourly_rate * project.exchange_rate
            budget_hours = budget_cost / rate_inr if rate_inr > 0 else Decimal('0')

            SubDepartment.objects.create(
                department=department,
                code=code,
                role_descrptn=role_descrptn,
                inkrement=inkrement,
                baseline_budget_cost=budget_cost,
                budget_hours=budget_hours,
                budget_cost=budget_cost,  # Direct storage
            )
        
        for dept in project.departments.all():
            total_dept_cost = sum(sub.budget_cost for sub in dept.sub_departments.all())
            dept.budget_cost = total_dept_cost
            dept.save()

        # Create ProjectCostCategory with baseline (unchanged)
        for cost_cat in CostCategory.objects.all():
            budget_cost = Decimal(str(cost_cat_budgets.get(cost_cat.code, '0')))

            ProjectCostCategory.objects.create(
                project=project,
                cost_category=cost_cat,
                baseline_budget_cost=budget_cost,
                budget_cost=budget_cost,
            )

        # === Generate First PSR Snapshot ===
        snapshot_date = project.created_at.date()

        try:
            call_command(
                'generate_psr_snapshot',
                str(project.co_no),
                '--date',
                snapshot_date.strftime('%Y-%m-%d'),
                '--frequency',
                'MONTHLY'
            )
        except Exception as e:
            print(f"Warning: Could not generate initial snapshot: {e}")

        return project

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        full_serializer = ProjectCreateSerializer(serializer.instance)
        return Response({
            "detail": "Project created successfully with initial financial plan and first PSR snapshot.",
            "project": full_serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)


class ProjectDetailView(APIView):
    # permission_classes = [IsAuthenticated]
    permission_classes = [AllowAny]

    def get(self, request, co_no):
        project = get_object_or_404(Project, co_no=co_no)

        # Base project data
        data = {
            "co_no": project.co_no,
            "project_name": project.project_name,
            "location": project.location,
            "project_manager": project.project_manager,
            "project_manager_email": project.project_manager_email,
            "sales_person": project.sales_person,
            "sales_person_email": project.sales_person_email,
            "sales_value_foreign_curr": float(project.sales_value_foreign_curr),
            "sales_value": float(project.sales_value),
            "ter_percentage": float(project.ter_percentage),
            "eff_percentage": float(project.eff_percentage),
            "budget": float(project.budget),
            "currency": project.currency,
            "exchange_rate": float(project.exchange_rate),
        }

        # Departments with rates and budget_hours
        department_budgets = {}
        for dept in project.departments.all():
            department_budgets[dept.name] = {
                "hourly_rate": float(dept.hourly_rate)
            }
        data["department_budgets"] = department_budgets

        # SubDepartments with budget_hours
        sub_department_budgets = {}
        for sub in SubDepartment.objects.filter(department__project=project):
            sub_department_budgets[sub.code] = float(sub.budget_cost)
        data["sub_department_budgets"] = sub_department_budgets

        # Cost categories with budget_cost
        cost_category_budgets = {}
        for pcc in project.project_cost_categories.all():
            cost_category_budgets[pcc.cost_category.code] = float(pcc.budget_cost)
        data["cost_category_budgets"] = cost_category_budgets

        return Response(data, status=status.HTTP_200_OK)


class ProjectUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    # permission_classes = [AllowAny]

    @transaction.atomic
    def patch(self, request, co_no):
        project = get_object_or_404(Project, co_no=co_no)

        # Update main project fields (partial)
        project_fields = [
            'project_name', 'location', 'project_manager', 'project_manager_email',
            'sales_person', 'sales_person_email', 'sales_value', 'ter_percentage', 'eff_percentage',
            'budget', 'currency', 'exchange_rate'
        ]
        for field in project_fields:
            if field in request.data:
                value = request.data[field]
                # Special handling for Decimal fields
                if field in ['sales_value', 'ter_percentage', 'eff_percentage', 'budget', 'exchange_rate']:
                    setattr(project, field, Decimal(str(value)) if value is not None else None)
                else:
                    setattr(project, field, value)
        project.save()

        # Update departments
        if 'department_budgets' in request.data:
            for dept_code, values in request.data['department_budgets'].items():
                dept = get_object_or_404(Department, project=project, name=dept_code)
                if 'hourly_rate' in values:
                    dept.hourly_rate = Decimal(str(values['hourly_rate']))
                if 'budget_hours' in values:
                    dept.budget_hours = Decimal(str(values['budget_hours']))
                dept.save()

        # Update sub-departments
        if 'sub_department_budgets' in request.data:
            for code, hours in request.data['sub_department_budgets'].items():
                sub = get_object_or_404(SubDepartment, department__project=project, code=code)
                sub.budget_hours = Decimal(str(hours))
                # Safe calculation: all values are Decimal
                sub.budget_cost = sub.budget_hours * sub.department.hourly_rate * project.exchange_rate
                sub.save()

        # Update cost categories
        if 'cost_category_budgets' in request.data:
            for code, cost in request.data['cost_category_budgets'].items():
                pcc = get_object_or_404(ProjectCostCategory, project=project, cost_category__code=code)
                pcc.budget_cost = Decimal(str(cost))
                pcc.save()

        return Response({
            "detail": "Project updated successfully.",
            "co_no": project.co_no
        }, status=status.HTTP_200_OK)



class ProjectKPIDetailsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, co_no):
        project = get_object_or_404(Project, co_no=co_no)
        serializer = ProjectBasicSerializer(project)
        return Response(serializer.data)


class ProjectStatusUpdateView(APIView):
    permission_classes = [AllowAny]

    def patch(self, request, co_no):
        project = get_object_or_404(Project, co_no=co_no)
        serializer = ProjectUpdateSerializer(
            project,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                "detail": "Project updated successfully",
                "data": ProjectBasicSerializer(project).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProjectLatestSnapshotKPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, co_no):
        project = get_object_or_404(Project, co_no=co_no)
        snapshot = PSRSnapshot.objects.filter(project=project).order_by('-snapshot_date').first()
        if not snapshot:
            return Response({"detail": "No snapshot available"}, status=status.HTTP_404_NOT_FOUND)
        serializer = PSRSnapshotKPISerializer(snapshot)
        return Response({
            "project": project.co_no,
            "snapshot_date": snapshot.snapshot_date,
            "kpi": serializer.data
        })


class ProjectSnapshotHistoryKPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, co_no):
        project = get_object_or_404(Project, co_no=co_no)
        snapshots = PSRSnapshot.objects.filter(project=project).order_by('snapshot_date')
        if not snapshots.exists():
            return Response({"detail": "No snapshots available"}, status=status.HTTP_404_NOT_FOUND)

        history = []
        for snapshot in snapshots:
            serializer = PSRSnapshotKPISerializer(snapshot)
            history.append({
                "snapshot_date": snapshot.snapshot_date.strftime('%Y-%m-%d'),
                "kpi": serializer.data
            })

        return Response({
            "project": project.co_no,
            "project_name": project.project_name,
            "history": history
        })


class LandingPageAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):

        projects = Project.objects.all()

        # Initialize aggregated totals
        total_sales_value = Decimal('0')
        total_budget = Decimal('0')
        total_ter = Decimal('0')
        total_eff = Decimal('0')
        total_actual = Decimal('0')
        total_forecast = Decimal('0')
        total_prognosis = Decimal('0')
        total_factors = Decimal('0')
        project_count = 0

        # Get latest snapshot for each project
        for project in projects:
            # Get the latest snapshot for this project
            latest_snapshot = PSRSnapshot.objects.filter(
                project=project
            ).order_by('-snapshot_date').first()

            # Add project values
            total_sales_value += project.sales_value or Decimal('0')

            # Add snapshot values if snapshot exists
            if latest_snapshot:
                
                total_budget += latest_snapshot.total_budget_cost or Decimal('0')
                total_ter += latest_snapshot.ter_value or Decimal('0')
                total_eff += latest_snapshot.eff_value or Decimal('0')
                total_actual += latest_snapshot.total_actual_cost or Decimal('0')
                total_forecast += latest_snapshot.total_forecast_cost or Decimal('0')
                total_prognosis += latest_snapshot.total_prognosis_cost or Decimal('0')
                
                # Add factor for averaging
                total_factors += latest_snapshot.factor or Decimal('0')
                project_count += 1

        # Calculate average factor
        average_factor = total_factors / project_count if project_count > 0 else Decimal('0')

        # Format the response - only the 8 fields for landing page
        return Response({
            "total_sales_value": float(total_sales_value),
            "total_budget": float(total_budget),
            "total_ter": float(total_ter),
            "total_eff": float(total_eff),
            "total_actual": float(total_actual),
            "total_forecast": float(total_forecast),
            "total_prognosis": float(total_prognosis),
            "average_factor": float(average_factor)
        }, status=status.HTTP_200_OK)



class AllProjectsLatestSnapshotView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Get all projects that have at least one snapshot
        projects_with_snapshots = Project.objects.filter(
            psr_snapshots__isnull=False
        ).distinct()

        project_data = []

        for project in projects_with_snapshots:
            snapshot = project.psr_snapshots.order_by('-snapshot_date').first()
            if snapshot:  # Should always exist due to filter
                data = {
                    "project_id": project.id,
                    "co_no": project.co_no,
                    "project_name": project.project_name,
                    "sales_value": float(project.sales_value),
                    "total_budget_cost": float(snapshot.total_budget_cost),
                    "ter_value": float(snapshot.ter_value),
                    "eff_value": float(snapshot.eff_value),
                    "total_actual_cost": float(snapshot.total_actual_cost),
                    "total_forecast_cost": float(snapshot.total_forecast_cost),
                    "total_prognosis_cost": float(snapshot.total_prognosis_cost),
                    "margin": float(snapshot.margin),
                    "factor": float(snapshot.factor),
                }
                project_data.append(data)

        return Response({
            "count": len(project_data),
            "projects_latest_snapshots": project_data
        })


class MonthlyCumulativeKPIHistoryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Get all snapshots ordered by date
        snapshots = PSRSnapshot.objects.all().order_by('snapshot_date')

        # Group by month (YYYY-MM)
        monthly_data = defaultdict(lambda: {
            'sales_value': Decimal('0'),
            'total_budget_cost': Decimal('0'),
            'ter_value': Decimal('0'),
            'eff_value': Decimal('0'),
            'total_actual_cost': Decimal('0'),
            'total_forecast_cost': Decimal('0'),
            'total_prognosis_cost': Decimal('0'),
            'margin': Decimal('0'),
            'factor_sum': Decimal('0'),
            'factor_count': 0
        })

        for snapshot in snapshots:
            month_key = snapshot.snapshot_date.strftime('%Y-%m')
            month_name = snapshot.snapshot_date.strftime('%B %Y')

            data = monthly_data[month_key]
            data['sales_value'] += snapshot.project.sales_value
            data['total_budget_cost'] += snapshot.total_budget_cost
            data['ter_value'] += snapshot.ter_value
            data['eff_value'] += snapshot.eff_value
            data['total_actual_cost'] += snapshot.total_actual_cost
            data['total_forecast_cost'] += snapshot.total_forecast_cost
            data['total_prognosis_cost'] += snapshot.total_prognosis_cost
            data['margin'] += snapshot.margin
            data['factor_sum'] += snapshot.factor
            data['factor_count'] += 1

        # Build final list in reverse chronological order
        history = []
        for month_key in sorted(monthly_data.keys(), reverse=True):
            month_name = datetime.strptime(month_key, '%Y-%m').strftime('%B %Y')
            data = monthly_data[month_key]
            average_factor = data['factor_sum'] / data['factor_count'] if data['factor_count'] > 0 else Decimal('0')

            history.append({
                "month": month_name,
                "sales_value": data['sales_value'],
                "total_budget_cost": data['total_budget_cost'],
                "ter_value": data['ter_value'],
                "eff_value": data['eff_value'],
                "total_actual_cost": data['total_actual_cost'],
                "total_forecast_cost": data['total_forecast_cost'],
                "total_prognosis_cost": data['total_prognosis_cost'],
                "margin": data['margin'],
                "factor": round(average_factor, 4),
            })

        serializer = MonthlyCumulativeKPISerializer(history, many=True)
        return Response({
            "months_count": len(history),
            "cumulative_kpi_history": serializer.data
        })



# class RKActualOverrideView(APIView):
#     permission_classes = [IsAuthenticated]

#     def patch(self, request, pk):
#         pcc = get_object_or_404(ProjectCostCategory, pk=pk)
        
#         # Validate it's RK
#         if pcc.cost_category.code != 'RK':
#             return Response(
#                 {"detail": "This endpoint is only for RK (Travel Costs) category."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         note = request.data.get('note')
#         lines = request.data.get('lines', [])

#         if not note:
#             return Response({"detail": "Note is required."}, status=status.HTTP_400_BAD_REQUEST)
#         if not lines or len(lines) == 0:
#             return Response({"detail": "At least one line with description and amount is required."}, status=status.HTTP_400_BAD_REQUEST)

#         with transaction.atomic():
#             # Get or create ONE adjustment record per ProjectCostCategory
#             adjustment, created = RKActualAdjustment.objects.get_or_create(
#                 project_cost_category=pcc,
#                 defaults={
#                     'adjusted_by': request.user,
#                     'note': note,
#                 }
#             )

#             if not created:
#                 # Update existing adjustment
#                 adjustment.note = note
#                 adjustment.adjusted_by = request.user
#                 adjustment.adjusted_at = timezone.now()
#                 adjustment.save()

#             # Clear old lines and add new ones
#             adjustment.lines.all().delete()  # Remove previous lines

#             total_amount = Decimal('0')
#             for line in lines:
#                 amount = Decimal(str(line.get('amount', 0)))
#                 if amount <= 0:
#                     return Response({"detail": "Each line must have positive amount."}, status=status.HTTP_400_BAD_REQUEST)

#                 RKActualAdjustmentLine.objects.create(
#                     adjustment=adjustment,
#                     description=line.get('description', ''),
#                     amount=amount
#                 )
#                 total_amount += amount

#             # Set override flag
#             pcc.actual_override = True
#             pcc.save()

#         # Regenerate latest snapshot
#         latest_snapshot = pcc.project.psr_snapshots.order_by('-snapshot_date').first()
#         if latest_snapshot:
#             call_command(
#                 'generate_psr_snapshot',
#                 str(pcc.project.co_no),
#                 '--date',
#                 latest_snapshot.snapshot_date.strftime('%Y-%m-%d')
#             )

#         serializer = RKActualAdjustmentSerializer(adjustment)
#         return Response({
#             "detail": "RK actuals updated successfully",
#             "current_total_actuals": float(total_amount),
#             "adjustment": serializer.data
#         }, status=status.HTTP_200_OK)



class RKActualOverrideView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        pcc = get_object_or_404(ProjectCostCategory, pk=pk)
        
        # Validate it's RK
        if pcc.cost_category.code != 'RK':
            return Response(
                {"detail": "This endpoint is only for RK (Travel Costs) category."},
                status=status.HTTP_400_BAD_REQUEST
            )

        note = request.data.get('note')
        lines = request.data.get('lines', [])

        if not note:
            return Response({"detail": "Note is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not lines or len(lines) == 0:
            return Response({"detail": "At least one line with description and amount is required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Get the latest adjustment or create new
            adjustment = pcc.rk_actual_adjustments.order_by('-adjusted_at').first()
            
            if adjustment:
                # Update existing
                adjustment.note = note
                adjustment.adjusted_by = request.user
                adjustment.adjusted_at = timezone.now()
                adjustment.save()
                
                # Delete old lines
                adjustment.lines.all().delete()
            else:
                # Create new if none exists
                adjustment = RKActualAdjustment.objects.create(
                    project_cost_category=pcc,
                    adjusted_by=request.user,
                    note=note
                )

            # Add all sent lines (full replacement)
            total_amount = Decimal('0')
            for line in lines:
                amount = Decimal(str(line.get('amount', '0')))
                if amount <= 0:
                    return Response({"detail": "Each line must have positive amount."}, status=status.HTTP_400_BAD_REQUEST)
                
                RKActualAdjustmentLine.objects.create(
                    adjustment=adjustment,
                    description=line.get('description', ''),
                    amount=amount
                )
                total_amount += amount

            # Set override flag
            pcc.actual_override = True
            pcc.save()

        # Regenerate latest snapshot
        latest_snapshot = pcc.project.psr_snapshots.order_by('-snapshot_date').first()
        if latest_snapshot:
            call_command('generate_psr_snapshot', str(pcc.project.co_no), '--date', latest_snapshot.snapshot_date.strftime('%Y-%m-%d'))

        serializer = RKActualAdjustmentSerializer(adjustment)
        return Response({
            "detail": "RK actuals updated successfully",
            "current_total_actuals": float(total_amount),
            "adjustment": serializer.data
        }, status=status.HTTP_200_OK)


# core/views.py

class RKGetActualOverrideView(APIView):
    permission_classes = [IsAuthenticated]
    # permission_classes = [AllowAny]

    def get(self, request, pk):
        pcc = get_object_or_404(ProjectCostCategory, pk=pk)

        # Validate it's RK
        if pcc.cost_category.code != 'RK':
            return Response(
                {"detail": "This endpoint is only for RK (Travel Costs) category."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if override is active
        if not pcc.actual_override:
            return Response({
                "actual_override": False,
                "detail": "No manual actuals override is active for RK. Using PO data (or zero)."
            }, status=status.HTTP_200_OK)

        # Get the latest adjustment (most recent)
        latest_adjustment = pcc.rk_actual_adjustments.order_by('-adjusted_at').first()

        if not latest_adjustment:
            return Response({
                "actual_override": True,
                "detail": "Override flag is set but no adjustment record found.",
                "current_total_actuals": 0.0,
            }, status=status.HTTP_200_OK)

        # Calculate current total from all lines (in case multiple adjustments)
        total_actuals = sum(line.amount for line in latest_adjustment.lines.all())

        # Serialize lines
        lines = []
        for line in latest_adjustment.lines.all():
            lines.append({
                "description": line.description,
                "amount": float(line.amount)
            })

        return Response({
            "actual_override": True,
            "current_total_actuals": float(total_actuals),
            "adjustment": {
                "id": latest_adjustment.id,
                "note": latest_adjustment.note,
                "adjusted_by": latest_adjustment.adjusted_by.username if latest_adjustment.adjusted_by else None,
                "adjusted_at": latest_adjustment.adjusted_at.isoformat(),
                "lines": lines
            }
        }, status=status.HTTP_200_OK)