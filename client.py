#!/usr/bin/env python3
"""
Marketing Campaign CLI Client
Interact with the marketing swarm backend
"""

import requests
import time
import sys
import json

API_URL = "http://localhost:8000"


class CampaignClient:
    def __init__(self):
        self.user_id = None
        self.current_session = None

    def request(self, method, endpoint, data=None):
        """Make API request"""
        headers = {"Content-Type": "application/json"}
        if self.user_id:
            headers["X-User-ID"] = self.user_id

        url = f"{API_URL}{endpoint}"
        try:
            if method == "GET":
                r = requests.get(url, headers=headers)
            elif method == "POST":
                r = requests.post(url, json=data, headers=headers)
            else:
                r = requests.delete(url, headers=headers)

            if r.status_code >= 400:
                return {"error": r.json().get("detail", "Request failed")}
            return r.json() if r.text else {}
        except Exception as e:
            return {"error": str(e)}

    def validate_x(self, access_token, access_secret):
        """Validate X credentials"""
        return self.request("POST", "/auth/validate-x", {
            "access_token": access_token,
            "access_secret": access_secret
        })

    def get_x_status(self):
        """Get X connection status"""
        return self.request("GET", "/auth/x-status")

    def create_campaign(self, name, description, audience, goals):
        """Create a new campaign"""
        return self.request("POST", "/campaign/create", {
            "name": name,
            "description": description,
            "target_audience": audience,
            "goals": goals,
            "duration_weeks": 3
        })

    def get_status(self, session_id):
        """Get campaign status"""
        return self.request("GET", f"/campaign/{session_id}/status")

    def get_plan(self, session_id):
        """Get campaign plan"""
        return self.request("GET", f"/campaign/{session_id}/plan")

    def approve_plan(self, session_id, approved, feedback=None):
        """Approve or reject plan"""
        return self.request("POST", f"/campaign/{session_id}/approve", {
            "approved": approved,
            "feedback": feedback
        })

    def run_daily(self, session_id):
        """Run daily swarms"""
        return self.request("POST", f"/campaign/{session_id}/run-daily")

    def get_stream(self, session_id):
        """Get stream logs"""
        return self.request("GET", f"/campaign/{session_id}/stream")

    def list_campaigns(self):
        """List all campaigns"""
        return self.request("GET", "/campaigns")

    def watch_stream(self, session_id):
        """Watch stream in real-time"""
        last_count = 0

        print("\n" + "=" * 60)
        print("  WATCHING SWARM STREAM")
        print("  Press Ctrl+C to stop")
        print("=" * 60 + "\n")

        try:
            while True:
                result = self.get_stream(session_id)
                logs = result.get("logs", [])
                status = result.get("status", "unknown")

                # Display new logs
                if len(logs) > last_count:
                    for log in logs[last_count:]:
                        agent = log.get("agent", "Unknown")
                        msg_type = log.get("type", "info")
                        content = log.get("content", "")

                        # Color coding
                        colors = {
                            "thinking": "\033[93m",
                            "action": "\033[94m",
                            "result": "\033[92m",
                            "error": "\033[91m"
                        }
                        color = colors.get(msg_type, "")
                        reset = "\033[0m"

                        print(f"{color}[{agent}] ({msg_type}) {content}{reset}")
                        sys.stdout.flush()

                    last_count = len(logs)

                # Check if complete
                if status in ["awaiting_approval", "daily_complete", "approved"]:
                    print(f"\n{'=' * 60}")
                    print(f"  STATUS: {status.upper()}")
                    print(f"{'=' * 60}\n")
                    break

                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n\nStopped watching stream.")


def main():
    client = CampaignClient()

    print("\n" + "=" * 60)
    print("  MARKETING CAMPAIGN CLIENT")
    print("=" * 60)

    # Get user ID
    client.user_id = input("\nEnter your User ID: ").strip()
    if not client.user_id:
        client.user_id = "user_" + str(int(time.time()))
        print(f"Generated User ID: {client.user_id}")

    # Main menu
    while True:
        x_status = client.get_x_status()
        campaigns = client.list_campaigns()
        campaign_list = campaigns.get("campaigns", [])

        print("\n" + "-" * 60)
        print(f"User: {client.user_id}")
        print(f"X Connected: {'✓ @' + x_status.get('username', '') if x_status.get('connected') else '✗'}")
        print(f"Active Campaigns: {len(campaign_list)}")

        if client.current_session:
            status = client.get_status(client.current_session)
            print(f"Current Session: {client.current_session[:8]}... ({status.get('status', 'unknown')})")

        print("-" * 60)

        print("\n[Setup]")
        print("1. Connect X Account")

        print("\n[Campaign]")
        print("2. Create New Campaign")
        print("3. View Campaign Plan")
        print("4. Approve Plan")
        print("5. Run Daily Swarms")

        print("\n[Monitor]")
        print("6. Watch Stream")
        print("7. View Status")
        print("8. List Campaigns")

        print("\n0. Exit")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            print("\n" + "=" * 60)
            print("  CONNECT X ACCOUNT")
            print("=" * 60)
            print("\nEnter your X API credentials:")
            token = input("Access Token: ").strip()
            secret = input("Access Token Secret: ").strip()

            if token and secret:
                result = client.validate_x(token, secret)
                if "error" in result:
                    print(f"\n✗ Error: {result['error']}")
                else:
                    print(f"\n✓ {result.get('message', 'Connected!')}")
            else:
                print("\n✗ Credentials required")

        elif choice == "2":
            print("\n" + "=" * 60)
            print("  CREATE NEW CAMPAIGN")
            print("=" * 60)

            name = input("\nCampaign Name: ").strip()
            description = input("Description (what are you promoting?): ").strip()
            audience = input("Target Audience: ").strip()

            print("\nEnter goals (one per line, empty line to finish):")
            goals = []
            while True:
                goal = input("  - ").strip()
                if not goal:
                    break
                goals.append(goal)

            if name and description:
                result = client.create_campaign(name, description, audience, goals)
                if "error" in result:
                    print(f"\n✗ Error: {result['error']}")
                else:
                    session_id = result.get("session_id")
                    client.current_session = session_id
                    print(f"\n✓ Campaign started!")
                    print(f"  Session ID: {session_id}")

                    watch = input("\nWatch stream now? (y/n) [y]: ").strip().lower()
                    if watch != "n":
                        client.watch_stream(session_id)
            else:
                print("\n✗ Name and description required")

        elif choice == "3":
            if not client.current_session:
                session = input("Session ID: ").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                plan = client.get_plan(client.current_session)
                if "error" in plan:
                    print(f"\n✗ Error: {plan['error']}")
                else:
                    print("\n" + "=" * 60)
                    print("  CAMPAIGN PLAN")
                    print("=" * 60)

                    print(f"\nStrategy: {plan.get('strategy_summary', 'N/A')}")

                    weeks = plan.get("weeks", [])
                    for week in weeks:
                        print(f"\n--- Week {week.get('week')} - {week.get('theme', '')} ---")
                        for post in week.get("posts", []):
                            print(f"  {post.get('day')} {post.get('time')}: {post.get('topic', '')}")
                            print(f"    Type: {post.get('type')} | {' '.join(post.get('hashtags', []))}")

        elif choice == "4":
            if not client.current_session:
                session = input("Session ID: ").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                approve = input("\nApprove this plan? (y/n): ").strip().lower()
                feedback = None
                if approve != "y":
                    feedback = input("Feedback for revision: ").strip()

                result = client.approve_plan(client.current_session, approve == "y", feedback)
                if "error" in result:
                    print(f"\n✗ Error: {result['error']}")
                else:
                    print(f"\n✓ {result.get('message', 'Done!')}")

        elif choice == "5":
            if not client.current_session:
                session = input("Session ID: ").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                result = client.run_daily(client.current_session)
                if "error" in result:
                    print(f"\n✗ Error: {result['error']}")
                else:
                    print(f"\n✓ {result.get('message', 'Started!')}")

                    watch = input("\nWatch stream now? (y/n) [y]: ").strip().lower()
                    if watch != "n":
                        client.watch_stream(client.current_session)

        elif choice == "6":
            if not client.current_session:
                session = input("Session ID: ").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                client.watch_stream(client.current_session)

        elif choice == "7":
            if not client.current_session:
                session = input("Session ID: ").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                status = client.get_status(client.current_session)
                if "error" in status:
                    print(f"\n✗ Error: {status['error']}")
                else:
                    print("\n" + "=" * 60)
                    print("  CAMPAIGN STATUS")
                    print("=" * 60)
                    print(f"\nSession: {status.get('session_id')}")
                    print(f"Status: {status.get('status')}")
                    print(f"Started: {status.get('started_at')}")

        elif choice == "8":
            campaigns = client.list_campaigns()
            campaign_list = campaigns.get("campaigns", [])

            print("\n" + "=" * 60)
            print("  YOUR CAMPAIGNS")
            print("=" * 60)

            if not campaign_list:
                print("\nNo campaigns found.")
            else:
                for i, camp in enumerate(campaign_list, 1):
                    print(f"\n{i}. {camp.get('session_id', '')[:8]}...")
                    print(f"   Status: {camp.get('status', 'unknown')}")
                    print(f"   Started: {camp.get('started_at', 'N/A')}")

                select = input("\nSelect campaign number (or Enter to skip): ").strip()
                if select.isdigit():
                    idx = int(select) - 1
                    if 0 <= idx < len(campaign_list):
                        client.current_session = campaign_list[idx]["session_id"]
                        print(f"\n✓ Selected session: {client.current_session[:8]}...")

        elif choice == "0":
            print("\nGoodbye!\n")
            break

        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
