# core/management/commands/import_timesheet.py

import os
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from core.models import TimesheetEntry


class Command(BaseCommand):
    help = "Import raw timesheet data from .xls/.xlsx file into TimesheetEntry dump table"

    def add_arguments(self, parser):
        parser.add_argument(
            'file',
            type=str,
            help="Filename (e.g., '20251031 Timesheet Report.xls') or full path"
        )
        parser.add_argument('--dry-run', action='store_true', help="Show what would be imported without saving")

    def handle(self, *args, **options):
        filename_or_path = options['file']
        dry_run = options['dry_run']

        # Resolve file path
        if os.path.isabs(filename_or_path):
            file_path = filename_or_path
        else:
            file_path = os.path.join(settings.BASE_DIR, filename_or_path)

        if not os.path.isfile(file_path):
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            self.stdout.write(f"Tip: Place the file in {settings.BASE_DIR}")
            return

        self.stdout.write(f"Importing timesheet: {os.path.basename(file_path)}")

        # Try different engines (xlrd for .xls, openpyxl for .xlsx)
        df = None
        for engine in ['xlrd', 'openpyxl']:
            try:
                df = pd.read_excel(
                    file_path,
                    sheet_name="Data",
                    skiprows=2,  # Headers are in row 3
                    engine=engine
                )
                self.stdout.write(f"Successfully read file with engine: {engine}")
                break
            except Exception as e:
                self.stdout.write(f"Engine {engine} failed: {e}")

        if df is None:
            self.stderr.write(self.style.ERROR("Failed to read the Excel file with any engine."))
            return

        if df.empty:
            self.stdout.write(self.style.WARNING("No data found in the 'Data' sheet."))
            return

        # Expected column names (adjust if your file uses different spelling/casing)
        required_columns = ['Date', 'EmpCd', 'EmpName', 'RoleDescrptn', 'CoNo', 'Hours']
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            self.stderr.write(self.style.ERROR(f"Missing required columns: {missing}"))
            self.stderr.write(f"Available columns: {list(df.columns)}")
            return

        total_rows = len(df)
        self.stdout.write(f"Found {total_rows} rows in file → processing...")

        # Keep only required columns
        df = df[required_columns].copy()

        # Drop rows missing any critical field
        df.dropna(subset=['Date', 'EmpCd', 'CoNo', 'Hours'], how='any', inplace=True)

        # Clean and convert
        df['CoNo'] = df['CoNo'].astype(str).str.strip()
        df['EmpCd'] = df['EmpCd'].astype(str).str.strip()
        df['EmpName'] = df['EmpName'].astype(str).str.strip()
        df['RoleDescrptn'] = df['RoleDescrptn'].astype(str).str.strip()

        # Convert Hours to numeric (invalid become NaN)
        df['Hours'] = pd.to_numeric(df['Hours'], errors='coerce')

        # Drop rows with invalid Hours or empty CoNo
        df.dropna(subset=['Hours'], inplace=True)
        df = df[df['CoNo'] != 'nan']
        df = df[df['CoNo'] != '']

        # Optional: Keep only valid project codes (length >= 5)
        # Remove this line if you want to import everything
        # df = df[df['CoNo'].str.len() >= 5]

        valid_count = len(df)
        self.stdout.write(f"{valid_count} valid rows after cleaning.")

        if valid_count == 0:
            self.stdout.write(self.style.WARNING("No valid data to import."))
            return

        # Prepare TimesheetEntry objects
        entries = []
        for _, row in df.iterrows():
            entries.append(TimesheetEntry(
                date=pd.to_datetime(row['Date']).date(),
                emp_cd=row['EmpCd'],
                emp_name=row['EmpName'],
                role_description=row['RoleDescrptn'],
                co_no=row['CoNo'],
                hours=row['Hours']
            ))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"[DRY RUN] Would import {len(entries)} TimesheetEntry records."))
            return

        # Bulk import with conflict handling
        start_time = timezone.now()
        with transaction.atomic():
            TimesheetEntry.objects.bulk_create(
                entries,
                ignore_conflicts=True,  # Skip duplicates based on unique constraint
                batch_size=5000
            )

        duration = (timezone.now() - start_time).total_seconds()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully imported {len(entries)} TimesheetEntry records in {duration:.2f} seconds"
            )
        )