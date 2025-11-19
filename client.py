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

# Color codes
class Colors:
    HEADER = '\033[95m'      # Magenta
    BLUE = '\033[94m'        # Blue
    CYAN = '\033[96m'        # Cyan
    GREEN = '\033[92m'       # Green
    YELLOW = '\033[93m'      # Yellow
    RED = '\033[91m'         # Red
    WHITE = '\033[97m'       # White
    BOLD = '\033[1m'         # Bold
    UNDERLINE = '\033[4m'    # Underline
    DIM = '\033[2m'          # Dim
    RESET = '\033[0m'        # Reset

def print_header(text):
    """Print a colored header"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{Colors.RESET}\n")

def print_subheader(text):
    """Print a colored subheader"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{text}{Colors.RESET}")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}{Colors.BOLD}✓ {text}{Colors.RESET}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}{Colors.BOLD}✗ {text}{Colors.RESET}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}{text}{Colors.RESET}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.WHITE}{text}{Colors.RESET}")

def print_menu_item(num, text, color=Colors.HEADER):
    """Print a menu item"""
    print(f"  {color}{Colors.BOLD}{num}.{Colors.RESET} {text}")

def print_divider():
    """Print a divider"""
    print(f"{Colors.DIM}{'-' * 60}{Colors.RESET}")


class CampaignClient:
    def __init__(self):
        self.user_id = None
        self.username = None
        self.token = None
        self.current_session = None

    def request(self, method, endpoint, data=None, auth_required=True):
        """Make API request"""
        headers = {"Content-Type": "application/json"}
        if auth_required and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

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

    def signup(self, username, email, password):
        """Create a new account"""
        return self.request("POST", "/auth/signup", {
            "username": username,
            "email": email,
            "password": password
        }, auth_required=False)

    def login(self, email, password):
        """Login to existing account"""
        return self.request("POST", "/auth/login", {
            "email": email,
            "password": password
        }, auth_required=False)

    def logout(self):
        """Logout current session"""
        return self.request("POST", "/auth/logout")

    def get_me(self):
        """Get current user info"""
        return self.request("GET", "/auth/me")

    def validate_x(self, consumer_key, consumer_secret, access_token, access_token_secret):
        """Validate X credentials using tweepy"""
        return self.request("POST", "/auth/validate-x", {
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret,
            "access_token": access_token,
            "access_token_secret": access_token_secret
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

    def get_stream(self, session_id):
        """Get stream logs"""
        return self.request("GET", f"/campaign/{session_id}/stream")

    def list_campaigns(self):
        """List all campaigns"""
        return self.request("GET", "/campaigns")

    def get_monitor(self, session_id):
        """Get full monitoring data"""
        return self.request("GET", f"/monitor/{session_id}")

    def get_strategic_map(self, session_id):
        """Get strategic map with progress"""
        return self.request("GET", f"/monitor/{session_id}/strategic-map")

    def create_strategy(self, name, description, audience, goals):
        """Create a 9-week strategic plan"""
        return self.request("POST", "/strategy/create", {
            "name": name,
            "description": description,
            "target_audience": audience,
            "goals": goals,
            "duration_weeks": 9
        })

    def get_strategy(self, session_id):
        """Get strategic plan"""
        return self.request("GET", f"/strategy/{session_id}")

    def get_strategy_table(self, session_id):
        """Get 9-week strategy table"""
        return self.request("GET", f"/strategy/{session_id}/table")

    def stop_campaign(self, session_id):
        """Stop a running campaign"""
        return self.request("POST", f"/monitor/{session_id}/stop")

    def resume_campaign(self, session_id):
        """Resume a stopped campaign"""
        return self.request("POST", f"/monitor/{session_id}/resume")

    def watch_stream(self, session_id):
        """Watch stream in real-time"""
        last_count = 0

        print_header("WATCHING SWARM STREAM")
        print_warning("Press Ctrl+C to stop\n")

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
                            "thinking": Colors.YELLOW,
                            "action": Colors.BLUE,
                            "result": Colors.GREEN,
                            "error": Colors.RED
                        }
                        color = colors.get(msg_type, Colors.WHITE)

                        print(f"{color}[{agent}] ({msg_type}) {content}{Colors.RESET}")
                        sys.stdout.flush()

                    last_count = len(logs)

                # Check if complete
                if status in ["awaiting_approval", "daily_complete", "approved", "running"]:
                    print(f"\n{Colors.CYAN}{'=' * 60}")
                    print(f"  STATUS: {status.upper()}")
                    print(f"{'=' * 60}{Colors.RESET}\n")
                    break

                time.sleep(0.5)

        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Stopped watching stream.{Colors.RESET}")


def main():
    client = CampaignClient()

    print_header("MARKETING CAMPAIGN CLIENT")

    # Authentication flow
    while not client.token:
        print_subheader("Authentication Required")
        print_menu_item("1", "Login", Colors.GREEN)
        print_menu_item("2", "Sign Up", Colors.CYAN)
        print(f"\n  {Colors.DIM}0. Exit{Colors.RESET}")

        auth_choice = input(f"\n{Colors.CYAN}{Colors.BOLD}Choice: {Colors.RESET}").strip()

        if auth_choice == "1":
            print_header("LOGIN")
            email = input(f"{Colors.CYAN}Email: {Colors.RESET}").strip()
            password = input(f"{Colors.CYAN}Password: {Colors.RESET}").strip()

            if email and password:
                result = client.login(email, password)
                if "error" in result:
                    print_error(f"Login failed: {result['error']}")
                else:
                    client.token = result.get("token")
                    client.user_id = result.get("user_id")
                    client.username = result.get("username")
                    print_success(f"Welcome back, {Colors.BOLD}{client.username}{Colors.RESET}!")
            else:
                print_error("Email and password required")

        elif auth_choice == "2":
            print_header("SIGN UP")
            username = input(f"{Colors.CYAN}Username: {Colors.RESET}").strip()
            email = input(f"{Colors.CYAN}Email: {Colors.RESET}").strip()
            password = input(f"{Colors.CYAN}Password: {Colors.RESET}").strip()
            confirm_password = input(f"{Colors.CYAN}Confirm Password: {Colors.RESET}").strip()

            if not all([username, email, password]):
                print_error("All fields are required")
            elif password != confirm_password:
                print_error("Passwords do not match")
            elif len(password) < 6:
                print_error("Password must be at least 6 characters")
            else:
                result = client.signup(username, email, password)
                if "error" in result:
                    print_error(f"Signup failed: {result['error']}")
                else:
                    client.token = result.get("token")
                    client.user_id = result.get("user_id")
                    client.username = result.get("username")
                    print_success(f"Account created! Welcome, {Colors.BOLD}{client.username}{Colors.RESET}!")

        elif auth_choice == "0":
            print(f"\n{Colors.CYAN}Goodbye!{Colors.RESET}\n")
            return

        if not client.token:
            input(f"\n{Colors.DIM}Press Enter to continue...{Colors.RESET}")

    # Main menu
    while True:
        x_status = client.get_x_status()
        campaigns = client.list_campaigns()
        campaign_list = campaigns.get("campaigns", [])

        print_divider()

        # Status bar
        print(f"\n{Colors.WHITE}{Colors.BOLD}User:{Colors.RESET} {Colors.CYAN}{client.username}{Colors.RESET} {Colors.DIM}({client.user_id[:8]}...){Colors.RESET}")

        if x_status.get('connected'):
            print(f"{Colors.WHITE}{Colors.BOLD}X Connected:{Colors.RESET} {Colors.GREEN}✓ @{x_status.get('username', x_status.get('email', 'Connected'))}{Colors.RESET}")
        else:
            print(f"{Colors.WHITE}{Colors.BOLD}X Connected:{Colors.RESET} {Colors.RED}✗ Not connected{Colors.RESET}")

        print(f"{Colors.WHITE}{Colors.BOLD}Active Campaigns:{Colors.RESET} {Colors.YELLOW}{len(campaign_list)}{Colors.RESET}")

        if client.current_session:
            status = client.get_status(client.current_session)
            status_text = status.get('status', 'unknown')
            status_color = Colors.GREEN if status_text in ['approved', 'running'] else Colors.YELLOW
            print(f"{Colors.WHITE}{Colors.BOLD}Current Session:{Colors.RESET} {Colors.DIM}{client.current_session[:8]}...{Colors.RESET} ({status_color}{status_text}{Colors.RESET})")

        print_divider()

        # Menu
        print_subheader("[Setup]")
        print_menu_item("1", "Connect X Account", Colors.CYAN)

        print_subheader("[Strategy]")
        print_menu_item("2", "Create 9-Week Strategy", Colors.HEADER)
        print_menu_item("3", "View Strategy Table", Colors.CYAN)

        print_subheader("[Campaign]")
        print_menu_item("4", "Create New Campaign", Colors.GREEN)
        print_menu_item("5", "View Campaign Plan", Colors.BLUE)
        print_menu_item("6", "Approve Plan", Colors.YELLOW)

        print_subheader("[Monitor]")
        print_menu_item("7", "Watch Stream", Colors.HEADER)
        print_menu_item("8", "View Strategic Map", Colors.CYAN)
        print_menu_item("9", "View Status", Colors.BLUE)
        print_menu_item("10", "List Campaigns", Colors.WHITE)

        print_subheader("[Control]")
        print_menu_item("11", "Stop Campaign", Colors.RED)
        print_menu_item("12", "Resume Campaign", Colors.GREEN)

        print_subheader("[Account]")
        print_menu_item("13", "Logout", Colors.DIM)

        print(f"\n  {Colors.DIM}0. Exit{Colors.RESET}")

        choice = input(f"\n{Colors.CYAN}{Colors.BOLD}Choice: {Colors.RESET}").strip()

        if choice == "1":
            print_header("CONNECT X ACCOUNT")
            print_info("Enter your X API credentials (from developer.twitter.com):\n")

            consumer_key = input(f"{Colors.CYAN}API Key (Consumer Key): {Colors.RESET}").strip()
            consumer_secret = input(f"{Colors.CYAN}API Secret (Consumer Secret): {Colors.RESET}").strip()
            access_token = input(f"{Colors.CYAN}Access Token: {Colors.RESET}").strip()
            access_token_secret = input(f"{Colors.CYAN}Access Token Secret: {Colors.RESET}").strip()

            if consumer_key and consumer_secret and access_token and access_token_secret:
                result = client.validate_x(consumer_key, consumer_secret, access_token, access_token_secret)
                if "error" in result:
                    print_error(f"Error: {result['error']}")
                else:
                    print_success(result.get('message', 'Connected!'))
            else:
                print_error("All four API credentials are required")

        elif choice == "2":
            print_header("CREATE 9-WEEK STRATEGY")

            name = input(f"{Colors.CYAN}Project Name: {Colors.RESET}").strip()
            description = input(f"{Colors.CYAN}Product Description: {Colors.RESET}").strip()
            audience = input(f"{Colors.CYAN}Target Audience: {Colors.RESET}").strip()

            print(f"\n{Colors.YELLOW}Enter goals (one per line, empty line to finish):{Colors.RESET}")
            goals = []
            while True:
                goal = input(f"  {Colors.DIM}-{Colors.RESET} ").strip()
                if not goal:
                    break
                goals.append(goal)

            if name and description:
                result = client.create_strategy(name, description, audience, goals)
                if "error" in result:
                    print_error(f"Error: {result['error']}")
                else:
                    session_id = result.get("session_id")
                    client.current_session = session_id
                    print_success("Strategy creation started!")
                    print_info(f"Session ID: {Colors.BOLD}{session_id}{Colors.RESET}")

                    watch = input(f"\n{Colors.YELLOW}Watch stream now? (y/n) [y]: {Colors.RESET}").strip().lower()
                    if watch != "n":
                        client.watch_stream(session_id)
            else:
                print_error("Name and description required")

        elif choice == "3":
            if not client.current_session:
                session = input(f"{Colors.CYAN}Session ID: {Colors.RESET}").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                strategy = client.get_strategy_table(client.current_session)
                if "error" in strategy:
                    print_error(f"Error: {strategy['error']}")
                else:
                    print_header("9-WEEK STRATEGY TABLE")

                    print(f"{Colors.WHITE}{Colors.BOLD}Overview:{Colors.RESET} {strategy.get('overview', 'N/A')}\n")

                    phases = strategy.get("phases", {})
                    for phase_name, phase_data in phases.items():
                        if not phase_data:
                            continue

                        theme = phase_data.get("theme", "")
                        weeks = phase_data.get("weeks", "")
                        print(f"\n{Colors.YELLOW}{Colors.BOLD}=== {phase_name.upper()} (Weeks {weeks}) - {theme} ==={Colors.RESET}")

                        for track in ["marketing", "operations", "feedback"]:
                            tasks = phase_data.get(track, [])
                            if tasks:
                                track_color = Colors.GREEN if track == "marketing" else Colors.BLUE if track == "operations" else Colors.CYAN
                                print(f"\n  {track_color}{Colors.BOLD}{track.upper()}:{Colors.RESET}")
                                for task in tasks:
                                    week = task.get("week", "?")
                                    task_desc = task.get("task", "")
                                    deliverable = task.get("deliverable", "")
                                    print(f"    {Colors.DIM}Week {week}:{Colors.RESET} {task_desc}")
                                    print(f"      {Colors.DIM}→ {deliverable}{Colors.RESET}")

                    # Milestones
                    milestones = strategy.get("milestones", [])
                    if milestones:
                        print(f"\n{Colors.HEADER}{Colors.BOLD}KEY MILESTONES:{Colors.RESET}")
                        for m in milestones:
                            print(f"  {Colors.CYAN}Week {m.get('week', '?')}:{Colors.RESET} {m.get('milestone', '')}")

                    # Budget
                    budget = strategy.get("budget", {})
                    if budget:
                        print(f"\n{Colors.HEADER}{Colors.BOLD}BUDGET ALLOCATION:{Colors.RESET}")
                        for area, allocation in budget.items():
                            print(f"  {Colors.WHITE}{area}:{Colors.RESET} {allocation}")

        elif choice == "4":
            print_header("CREATE NEW CAMPAIGN")

            name = input(f"{Colors.CYAN}Campaign Name: {Colors.RESET}").strip()
            description = input(f"{Colors.CYAN}Description (what are you promoting?): {Colors.RESET}").strip()
            audience = input(f"{Colors.CYAN}Target Audience: {Colors.RESET}").strip()

            print(f"\n{Colors.YELLOW}Enter goals (one per line, empty line to finish):{Colors.RESET}")
            goals = []
            while True:
                goal = input(f"  {Colors.DIM}-{Colors.RESET} ").strip()
                if not goal:
                    break
                goals.append(goal)

            if name and description:
                result = client.create_campaign(name, description, audience, goals)
                if "error" in result:
                    print_error(f"Error: {result['error']}")
                else:
                    session_id = result.get("session_id")
                    client.current_session = session_id
                    print_success("Campaign started!")
                    print_info(f"Session ID: {Colors.BOLD}{session_id}{Colors.RESET}")

                    watch = input(f"\n{Colors.YELLOW}Watch stream now? (y/n) [y]: {Colors.RESET}").strip().lower()
                    if watch != "n":
                        client.watch_stream(session_id)
            else:
                print_error("Name and description required")

        elif choice == "5":
            if not client.current_session:
                session = input(f"{Colors.CYAN}Session ID: {Colors.RESET}").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                plan = client.get_plan(client.current_session)
                if "error" in plan:
                    print_error(f"Error: {plan['error']}")
                else:
                    print_header("CAMPAIGN PLAN")

                    print(f"{Colors.WHITE}{Colors.BOLD}Strategy:{Colors.RESET} {plan.get('strategy_summary', 'N/A')}")

                    weeks = plan.get("weeks", [])
                    for week in weeks:
                        print(f"\n{Colors.YELLOW}{Colors.BOLD}--- Week {week.get('week')} - {week.get('theme', '')} ---{Colors.RESET}")
                        for post in week.get("posts", []):
                            print(f"  {Colors.CYAN}{post.get('day')} {post.get('time')}:{Colors.RESET} {post.get('topic', '')}")
                            print(f"    {Colors.DIM}Type: {post.get('type')} | {' '.join(post.get('hashtags', []))}{Colors.RESET}")

        elif choice == "6":
            if not client.current_session:
                session = input(f"{Colors.CYAN}Session ID: {Colors.RESET}").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                approve = input(f"\n{Colors.YELLOW}Approve this plan? (y/n): {Colors.RESET}").strip().lower()
                feedback = None
                if approve != "y":
                    feedback = input(f"{Colors.CYAN}Feedback for revision: {Colors.RESET}").strip()

                result = client.approve_plan(client.current_session, approve == "y", feedback)
                if "error" in result:
                    print_error(f"Error: {result['error']}")
                else:
                    print_success(result.get('message', 'Done!'))

        elif choice == "7":
            if not client.current_session:
                session = input(f"{Colors.CYAN}Session ID: {Colors.RESET}").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                client.watch_stream(client.current_session)

        elif choice == "8":
            if not client.current_session:
                session = input(f"{Colors.CYAN}Session ID: {Colors.RESET}").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                strategic_map = client.get_strategic_map(client.current_session)
                if "error" in strategic_map:
                    print_error(f"Error: {strategic_map['error']}")
                else:
                    print_header("STRATEGIC MAP")

                    # Progress overview
                    progress = strategic_map.get("progress", {})
                    print(f"{Colors.WHITE}{Colors.BOLD}Overall Progress:{Colors.RESET} {Colors.GREEN}{progress.get('completion_percentage', 0):.1f}%{Colors.RESET}")
                    print(f"{Colors.WHITE}Completed: {Colors.GREEN}{progress.get('completed', 0)}{Colors.RESET} | In Progress: {Colors.YELLOW}{progress.get('in_progress', 0)}{Colors.RESET} | Pending: {Colors.DIM}{progress.get('pending', 0)}{Colors.RESET}")

                    current = strategic_map.get("current_position", {})
                    print(f"\n{Colors.CYAN}{Colors.BOLD}Current Position:{Colors.RESET} {current.get('description', 'Not started')}")

                    # Strategy info
                    print(f"\n{Colors.WHITE}{Colors.BOLD}Strategy:{Colors.RESET} {strategic_map.get('strategy_summary', 'N/A')}")

                    # Weekly breakdown
                    for week in strategic_map.get("strategic_map", []):
                        week_status = week.get("status", "pending")
                        status_color = Colors.GREEN if week_status == "completed" else Colors.YELLOW if week_status == "in_progress" else Colors.DIM

                        print(f"\n{Colors.YELLOW}{Colors.BOLD}Week {week.get('week')} - {week.get('theme', '')}{Colors.RESET}")
                        print(f"{status_color}Completion: {week.get('completion_percentage', 0):.0f}%{Colors.RESET}")

                        for post in week.get("posts", []):
                            status = post.get("status", "pending")
                            if status == "completed":
                                icon = f"{Colors.GREEN}✓{Colors.RESET}"
                            elif status == "in_progress":
                                icon = f"{Colors.YELLOW}◐{Colors.RESET}"
                            else:
                                icon = f"{Colors.DIM}○{Colors.RESET}"

                            print(f"  {icon} {Colors.CYAN}{post.get('day')} {post.get('time')}:{Colors.RESET} {post.get('topic', '')[:50]}")

        elif choice == "9":
            if not client.current_session:
                session = input(f"{Colors.CYAN}Session ID: {Colors.RESET}").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                status = client.get_status(client.current_session)
                if "error" in status:
                    print_error(f"Error: {status['error']}")
                else:
                    print_header("CAMPAIGN STATUS")
                    print(f"{Colors.WHITE}{Colors.BOLD}Session:{Colors.RESET} {status.get('session_id')}")

                    status_text = status.get('status', 'unknown')
                    status_color = Colors.GREEN if status_text in ['approved', 'running', 'daily_complete', 'strategy_complete'] else Colors.YELLOW
                    print(f"{Colors.WHITE}{Colors.BOLD}Status:{Colors.RESET} {status_color}{status_text}{Colors.RESET}")
                    print(f"{Colors.WHITE}{Colors.BOLD}Started:{Colors.RESET} {status.get('started_at')}")

        elif choice == "10":
            campaigns = client.list_campaigns()
            campaign_list = campaigns.get("campaigns", [])

            print_header("YOUR CAMPAIGNS")

            if not campaign_list:
                print_warning("No campaigns found.")
            else:
                for i, camp in enumerate(campaign_list, 1):
                    status = camp.get('status', 'unknown')
                    status_color = Colors.GREEN if status in ['approved', 'running', 'strategy_complete'] else Colors.YELLOW

                    print(f"\n{Colors.CYAN}{Colors.BOLD}{i}.{Colors.RESET} {camp.get('session_id', '')[:8]}...")
                    print(f"   {Colors.WHITE}Status:{Colors.RESET} {status_color}{status}{Colors.RESET}")
                    print(f"   {Colors.WHITE}Started:{Colors.RESET} {Colors.DIM}{camp.get('started_at', 'N/A')}{Colors.RESET}")

                select = input(f"\n{Colors.YELLOW}Select campaign number (or Enter to skip): {Colors.RESET}").strip()
                if select.isdigit():
                    idx = int(select) - 1
                    if 0 <= idx < len(campaign_list):
                        client.current_session = campaign_list[idx]["session_id"]
                        print_success(f"Selected session: {client.current_session[:8]}...")

        elif choice == "11":
            if not client.current_session:
                session = input(f"{Colors.CYAN}Session ID: {Colors.RESET}").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                confirm = input(f"{Colors.RED}Are you sure you want to stop the campaign? (y/n): {Colors.RESET}").strip().lower()
                if confirm == "y":
                    result = client.stop_campaign(client.current_session)
                    if "error" in result:
                        print_error(f"Error: {result['error']}")
                    else:
                        print_success(result.get('message', 'Campaign stopped'))

        elif choice == "12":
            if not client.current_session:
                session = input(f"{Colors.CYAN}Session ID: {Colors.RESET}").strip()
                if session:
                    client.current_session = session

            if client.current_session:
                result = client.resume_campaign(client.current_session)
                if "error" in result:
                    print_error(f"Error: {result['error']}")
                else:
                    print_success(result.get('message', 'Campaign resumed'))

        elif choice == "13":
            confirm = input(f"{Colors.YELLOW}Are you sure you want to logout? (y/n): {Colors.RESET}").strip().lower()
            if confirm == "y":
                result = client.logout()
                if "error" in result:
                    print_error(f"Error: {result['error']}")
                else:
                    print_success("Logged out successfully")
                    client.token = None
                    client.user_id = None
                    client.username = None
                    client.current_session = None
                    print(f"\n{Colors.CYAN}Goodbye!{Colors.RESET}\n")
                    break

        elif choice == "0":
            print(f"\n{Colors.CYAN}Goodbye!{Colors.RESET}\n")
            break

        input(f"\n{Colors.DIM}Press Enter to continue...{Colors.RESET}")


if __name__ == "__main__":
    main()
