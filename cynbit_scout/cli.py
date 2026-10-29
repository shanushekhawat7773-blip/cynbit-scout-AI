"""
Command-Line Interface (CLI) for Cynbit Scout.
Enables headless single inquiry qualification, batch CSV processing, and pipeline automation.
"""

import argparse
import json
import os
import sys

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cynbit_scout.models.schemas import RawInquiryInput
from cynbit_scout.pipeline import LeadIntelligencePipeline


def main():
    parser = argparse.ArgumentParser(
        description="Cynbit Scout CLI - AI Discovery & Lead Intelligence Pipeline"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: Single inquiry analysis
    single_parser = subparsers.add_parser("analyze", help="Analyze a single unstructured inquiry")
    single_parser.add_argument("--text", required=True, help="Raw inquiry or problem statement text")
    single_parser.add_argument("--name", default=None, help="Prospective client contact name")
    single_parser.add_argument("--email", default=None, help="Contact email address")
    single_parser.add_argument("--company", default=None, help="Organization / company name")
    single_parser.add_argument("--mode", default="hybrid", choices=["hybrid", "rules_only", "llm_only"], help="Processing mode")
    single_parser.add_argument("--json", action="store_true", help="Output full record as JSON")

    # Subcommand: Batch CSV processing
    batch_parser = subparsers.add_parser("batch", help="Batch process a CSV file of inquiries")
    batch_parser.add_argument("--input", required=True, help="Path to input CSV file")
    batch_parser.add_argument("--export", default=None, help="Path to export qualified CSV results")
    batch_parser.add_argument("--mode", default="rules_only", choices=["hybrid", "rules_only"], help="Processing mode")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    pipeline = LeadIntelligencePipeline(default_mode=args.mode)

    if args.command == "analyze":
        inquiry = RawInquiryInput(
            raw_text=args.text,
            sender_name=args.name,
            sender_email=args.email,
            company_name=args.company,
            source="cli"
        )
        try:
            record = pipeline.process_single(inquiry, force_mode=args.mode, save_to_db=True)
            if args.json:
                print(record.model_dump_json(indent=2))
            else:
                print("\n" + "=" * 60)
                print(f"CYNBIT SCOUT LEAD INTELLIGENCE REPORT [ID: {record.id[:8]}...]")
                print("=" * 60)
                print(f"Mode:            {record.processing_mode.value}")
                print(f"Priority Score:  {record.priority_score}/100 [{record.priority_tier.value}]")
                print(f"Services:        {', '.join(s.value for s in record.extracted.services)}")
                print(f"Budget Tier:     {record.extracted.budget_tier.value}")
                print(f"Urgency:         {record.extracted.urgency.value}")
                print(f"Industry:        {record.extracted.industry}")
                if record.injection_detected:
                    print("SECURITY:        ALERT - Prompt injection attempt intercepted!")
                print("\nEXECUTIVE SUMMARY:")
                print(record.summary)
                print("\nCLARIFYING QUESTIONS:")
                for i, q in enumerate(record.follow_up_questions, 1):
                    print(f"  {i}. {q}")
                print("\n" + record.draft_reply)
                print("=" * 60 + "\n")
        except Exception as e:
            print(f"Error during analysis: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "batch":
        import pandas as pd
        if not os.path.exists(args.input):
            print(f"Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)

        df = pd.read_csv(args.input)
        records = df.to_dict(orient="records")
        print(f"Ingesting and processing {len(records)} rows from {args.input}...")

        valid_leads, rejected = pipeline.process_batch(records, force_mode=args.mode)
        print(f"Completed: {len(valid_leads)} leads qualified & stored. {len(rejected)} rows rejected.")

        if args.export:
            export_df = pipeline.db.export_to_dataframe()
            export_df.to_csv(args.export, index=False)
            print(f"Exported complete database to {args.export}")


if __name__ == "__main__":
    main()
