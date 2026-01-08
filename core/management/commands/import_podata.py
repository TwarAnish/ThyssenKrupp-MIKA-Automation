# core/management/commands/import_podata.py

import os
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from core.models import POData


class Command(BaseCommand):
    help = "Import raw PO data from .xls/.xlsx file into POData dump table"

    def add_arguments(self, parser):
        parser.add_argument(
            'file',
            type=str,
            help="Filename (e.g., '20251031 PO Data.xls') or full path"
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

        self.stdout.write(f"Importing PO data: {os.path.basename(file_path)}")

        # Read Excel
        df = None
        for engine in ['openpyxl', 'xlrd']:
            try:
                df = pd.read_excel(
                    file_path,
                    sheet_name="Data",
                    skiprows=2,
                    engine=engine
                )
                self.stdout.write(f"Successfully read with engine: {engine}")
                break
            except Exception as e:
                self.stdout.write(f"Engine {engine} failed: {e}")

        if df is None:
            self.stderr.write(self.style.ERROR("Could not read the Excel file with any engine."))
            return

        if df.empty:
            self.stdout.write(self.style.WARNING("No data found in the 'Data' sheet."))
            return

        # Required columns from your file
        required_cols = ['PoNo', 'Po.Date', 'SrNo', 'CONo', 'ProjName', 'MatCode', 'POValue in Local Curr']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            self.stderr.write(self.style.ERROR(f"Missing required columns: {missing}"))
            return

        total_rows = len(df)
        self.stdout.write(f"Found {total_rows} rows in file.")

        # Clean and filter
        df = df[required_cols + ['ItemCode', 'Description', 'SupplierName']].copy()
        df.dropna(subset=['CONo', 'POValue in Local Curr'], inplace=True)
        df['CONo'] = df['CONo'].astype(str).str.strip()
        df['POValue in Local Curr'] = pd.to_numeric(df['POValue in Local Curr'], errors='coerce')
        df.dropna(subset=['POValue in Local Curr'], inplace=True)

        valid_count = len(df)
        self.stdout.write(f"{valid_count} valid rows after cleaning.")

        if valid_count == 0:
            self.stdout.write(self.style.WARNING("No valid data to import."))
            return

        # Prepare objects
        entries = []
        for _, row in df.iterrows():
            entries.append(POData(
                po_no=str(row['PoNo']).strip() if pd.notna(row['PoNo']) else "",
                po_date=row['Po.Date'] if pd.notna(row['Po.Date']) else None,
                sr_no=int(row['SrNo']) if pd.notna(row['SrNo']) and str(row['SrNo']).strip().isdigit() else None,
                co_no=row['CONo'],
                project_name=str(row['ProjName']).strip() if pd.notna(row['ProjName']) else "",
                mat_code=str(row['MatCode']).strip() if pd.notna(row['MatCode']) else "UNKNOWN",
                po_value_inr=row['POValue in Local Curr'],
                item_code=str(row.get('ItemCode', '')).strip(),
                description=str(row.get('Description', '')).strip(),
                supplier_name=str(row.get('SupplierName', '')).strip(),
            ))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"[DRY RUN] Would import {len(entries)} records."))
            return

        # Bulk import with conflict handling
        start_time = timezone.now()
        with transaction.atomic():
            imported_count = 0
            batch_size = 5000
            for i in range(0, len(entries), batch_size):
                batch = entries[i:i + batch_size]
                created = POData.objects.bulk_create(
                    batch,
                    update_conflicts=True,
                    update_fields=['po_value_inr', 'updated_at'],  # Update value if duplicate
                    unique_fields=['co_no', 'po_no', 'sr_no']
                )
                imported_count += len(created)

        duration = (timezone.now() - start_time).total_seconds()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully imported/updated {imported_count} POData records in {duration:.2f}s"
            )
    )