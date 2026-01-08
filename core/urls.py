# core/urls.py

from django.urls import path
from .views import (
                    ProjectPSRSnapshotTimesheetView, ProjectPSRSnapshotCostToGoView,
                    ProjectSnapshotTimesheetHistoryView, ProjectSnapshotCostToGoHistoryView,
                    SubDepartmentBudgetUpdateView, ProjectCostCategoryBudgetUpdateView,
                    SubDepartmentGetForecastOverrideView, ProjectCostCategoryGetForecastOverrideView,
                    SubDepartmentForecastOverrideView, ProjectCostCategoryForecastOverrideView, 
                    ProjectCreateView, ProjectDetailView, ProjectUpdateView,
                    ProjectKPIDetailsView, ProjectStatusUpdateView,
                    ProjectLatestSnapshotKPIView, ProjectSnapshotHistoryKPIView,
                    LandingPageAPIView, AllProjectsLatestSnapshotView, MonthlyCumulativeKPIHistoryView,
                    RKActualOverrideView, RKGetActualOverrideView)

urlpatterns = [
    
    path('landing-data/', LandingPageAPIView.as_view(), name='landing-page-summary'),
    
    path('projects/latest-snapshots/', AllProjectsLatestSnapshotView.as_view(), name='all-projects-latest-snapshots'),
    path('projects/history-kpi/', MonthlyCumulativeKPIHistoryView.as_view(), name='monthly-cumulative-kpi-history'),
    
    path('projects/<str:co_no>/snapshot/timesheet/', ProjectPSRSnapshotTimesheetView.as_view(), name='project-snapshot-timesheet'),
    path('projects/<str:co_no>/snapshot/timesheet/<str:snapshot_date>/', ProjectPSRSnapshotTimesheetView.as_view(), name='project-snapshot-timesheet-date'),

    path('projects/<str:co_no>/snapshot/cost-to-go/', ProjectPSRSnapshotCostToGoView.as_view(), name='project-snapshot-cost-to-go'),
    path('projects/<str:co_no>/snapshot/cost-to-go/<str:snapshot_date>/', ProjectPSRSnapshotCostToGoView.as_view(), name='project-snapshot-cost-to-go-date'),
    
    path('projects/<str:co_no>/snapshot-history/timesheet/', ProjectSnapshotTimesheetHistoryView.as_view(), name='project-snapshot-timesheet-history'),
    path('projects/<str:co_no>/snapshot-history/cost-to-go/', ProjectSnapshotCostToGoHistoryView.as_view(), name='project-snapshot-cost-to-go-history'),
    
    path('subdepartments/<int:pk>/budget-update/', SubDepartmentBudgetUpdateView.as_view(), name='subdepartment-budget-update'),
    path('projectcostcategories/<int:pk>/budget-update/', ProjectCostCategoryBudgetUpdateView.as_view(), name='projectcostcategory-budget-update'),
    
    path('subdepartments/<int:pk>/forecast-override/', SubDepartmentForecastOverrideView.as_view(), name='subdepartment-forecast-override'),
    path('subdepartments/<int:pk>/get-forecast-override/', SubDepartmentGetForecastOverrideView.as_view(), name='subdepartment-forecast-override'),
    
    path('projectcostcategories/<int:pk>/forecast-override/', ProjectCostCategoryForecastOverrideView.as_view(), name='projectcostcategory-forecast-override'),
    path('projectcostcategories/<int:pk>/get-forecast-override/', ProjectCostCategoryGetForecastOverrideView.as_view(), name='projectcostcategory-forecast-override-detail'),
    
    path('projects/', ProjectCreateView.as_view(), name='project-create'),
    path('projects/<str:co_no>/', ProjectDetailView.as_view(), name='project-detail'),
    path('projects/<str:co_no>/update/', ProjectUpdateView.as_view(), name='project-update'),
    
    path('projects/<str:co_no>/details/', ProjectKPIDetailsView.as_view(), name='project-details'),
    path('projects/<str:co_no>/update-status/', ProjectStatusUpdateView.as_view(), name='project-update'),
    path('projects/<str:co_no>/snapshot/latest-kpi/', ProjectLatestSnapshotKPIView.as_view(), name='project-latest-kpi'),
    path('projects/<str:co_no>/snapshot/history-kpi/', ProjectSnapshotHistoryKPIView.as_view(), name='project-history-kpi'),

    path('projectcostcategories/<int:pk>/rk-actual-override/', RKActualOverrideView.as_view(), name='rk-actual-override'),
    path('projectcostcategories/<int:pk>/get-rk-actual-override/', RKGetActualOverrideView.as_view(), name='rk-actual-override-detail'),
]