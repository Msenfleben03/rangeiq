#!/usr/bin/env python3
"""
Test script for CBBData REST API

Tests direct HTTP access to Barttorvik T-Rank historical ratings.

Usage:
    1. Get API key:
       python test_cbbdata_api.py --register username password email
       (Note: Registration may require R package, try login first)

    2. Test login:
       python test_cbbdata_api.py --login username password

    3. Test archive endpoint:
       python test_cbbdata_api.py --test-archive API_KEY

    4. Test date queries:
       python test_cbbdata_api.py --test-dates API_KEY

    5. Save sample data:
       python test_cbbdata_api.py --save-sample API_KEY 2023
"""

import argparse
import json
import sys
from pathlib import Path

import requests


class CBBDataAPITester:
    """Test client for CBBData REST API"""

    BASE_URL = "https://www.cbbdata.com/api"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "CBBDataAPITester/1.0", "Accept": "application/json"}
        )

    def login(self, username: str, password: str) -> dict:
        """
        Login to get API key

        Args:
            username: Account username
            password: Account password

        Returns:
            Response dict with 'api_key' field
        """
        url = f"{self.BASE_URL}/auth/login"
        payload = {"username": username, "password": password}

        print(f"POST {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")

        try:
            response = self.session.post(url, json=payload, timeout=10)
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")

            if response.status_code == 200:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
                if "api_key" in data:
                    self.api_key = data["api_key"]
                    print(f"\nAPI Key obtained: {self.api_key[:20]}...")
                return data
            else:
                print(f"Error: {response.text}")
                return {"error": response.text, "status_code": response.status_code}
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return {"error": str(e)}

    def test_archive_basic(self, year: int = 2023) -> dict:
        """
        Test basic archive endpoint

        Args:
            year: Season year to query

        Returns:
            Response dict
        """
        if not self.api_key:
            return {"error": "API key required"}

        url = f"{self.BASE_URL}/torvik/ratings/archive"
        params = {"year": year, "key": self.api_key}

        print(f"\nGET {url}")
        print(f"Params: {params}")

        try:
            response = self.session.get(url, params=params, timeout=30)
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type')}")
            print(f"Content-Length: {response.headers.get('Content-Length', 'unknown')}")

            if response.status_code == 200:
                # Try to parse JSON
                try:
                    data = response.json()
                    print("\nJSON Response received")
                    print(f"Type: {type(data)}")

                    if isinstance(data, list):
                        print(f"Records: {len(data)}")
                        if data:
                            print("\nFirst record:")
                            print(json.dumps(data[0], indent=2))
                            print(f"\nFields: {list(data[0].keys())}")

                            # Check for date fields
                            date_fields = [
                                k
                                for k in data[0].keys()
                                if "date" in k.lower() or "day" in k.lower()
                            ]
                            if date_fields:
                                print(f"\nDate-related fields found: {date_fields}")
                            else:
                                print("\nWARNING: No obvious date fields found")
                    elif isinstance(data, dict):
                        print(f"Keys: {list(data.keys())}")
                        print(json.dumps(data, indent=2)[:500])

                    return data
                except json.JSONDecodeError:
                    print("Not JSON - Content preview:")
                    print(response.text[:500])
                    return {"error": "Not JSON", "content": response.text[:200]}
            else:
                print(f"Error: {response.text}")
                return {"error": response.text, "status_code": response.status_code}
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return {"error": str(e)}

    def test_archive_with_filters(self, year: int = 2023, conf: str = "ACC") -> dict:
        """
        Test archive endpoint with filters

        Args:
            year: Season year
            conf: Conference abbreviation

        Returns:
            Response dict
        """
        if not self.api_key:
            return {"error": "API key required"}

        url = f"{self.BASE_URL}/torvik/ratings/archive"
        params = {"year": year, "conf": conf, "key": self.api_key}

        print(f"\nGET {url}")
        print(f"Params: {params}")

        try:
            response = self.session.get(url, params=params, timeout=30)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"Filtered records: {len(data) if isinstance(data, list) else 'N/A'}")
                return data
            else:
                print(f"Error: {response.text}")
                return {"error": response.text}
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return {"error": str(e)}

    def test_date_queries(self) -> dict:
        """
        Test various date query formats

        Returns:
            Dict with results for each format
        """
        if not self.api_key:
            return {"error": "API key required"}

        url = f"{self.BASE_URL}/torvik/ratings/archive"
        test_cases = [
            {"year": 2023, "date": "20230115"},
            {"year": 2023, "date": "2023-01-15"},
            {"year": 2023, "start_date": "20230115", "end_date": "20230120"},
            {"year": 2023, "day_num": 50},
            {"year": 2023, "day": 50},
        ]

        results = {}
        for i, params in enumerate(test_cases, 1):
            params["key"] = self.api_key
            print(f"\nTest {i}: {params}")

            try:
                response = self.session.get(url, params=params, timeout=10)
                print(f"Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    count = len(data) if isinstance(data, list) else "N/A"
                    print(f"Records: {count}")
                    results[f"test_{i}"] = {"success": True, "count": count, "params": params}
                else:
                    print(f"Error: {response.text[:200]}")
                    results[f"test_{i}"] = {"success": False, "error": response.text[:200]}
            except Exception as e:
                print(f"Failed: {e}")
                results[f"test_{i}"] = {"success": False, "error": str(e)}

        return results

    def save_sample_data(self, year: int, output_dir: str = "data/external") -> None:
        """
        Save sample archive data to file

        Args:
            year: Season year
            output_dir: Output directory
        """
        if not self.api_key:
            print("ERROR: API key required")
            return

        print(f"\nFetching full archive for {year}...")
        data = self.test_archive_basic(year)

        if isinstance(data, list) and data:
            output_path = Path(output_dir) / f"barttorvik_archive_{year}_sample.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            print(f"\nSaved {len(data)} records to {output_path}")

            # Also save schema analysis
            schema_path = output_path.with_suffix(".schema.json")
            schema = self._analyze_schema(data)
            with open(schema_path, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2)
            print(f"Saved schema analysis to {schema_path}")
        else:
            print(f"ERROR: Could not fetch data - {data}")

    def _analyze_schema(self, data: list[dict]) -> dict:
        """Analyze schema of returned data"""
        if not data:
            return {}

        first_record = data[0]
        schema = {
            "total_records": len(data),
            "fields": {},
            "date_fields": [],
            "sample_record": first_record,
        }

        for key, value in first_record.items():
            schema["fields"][key] = {"type": type(value).__name__, "sample": str(value)[:100]}
            if any(kw in key.lower() for kw in ["date", "day", "time"]):
                schema["date_fields"].append(key)

        return schema


def main():
    parser = argparse.ArgumentParser(description="Test CBBData REST API")
    parser.add_argument(
        "--login", nargs=2, metavar=("USERNAME", "PASSWORD"), help="Login and get API key"
    )
    parser.add_argument("--test-archive", metavar="API_KEY", help="Test archive endpoint")
    parser.add_argument("--test-dates", metavar="API_KEY", help="Test date query formats")
    parser.add_argument(
        "--save-sample", nargs=2, metavar=("API_KEY", "YEAR"), help="Save sample archive data"
    )
    parser.add_argument(
        "--year", type=int, default=2023, help="Year for archive queries (default: 2023)"
    )

    args = parser.parse_args()

    if args.login:
        username, password = args.login
        tester = CBBDataAPITester()
        result = tester.login(username, password)
        if "api_key" in result:
            print("\n✓ Login successful!")
            print("\nUse this API key for testing:")
            print(f"  --test-archive {result['api_key']}")
        else:
            print("\n✗ Login failed")
            sys.exit(1)

    elif args.test_archive:
        tester = CBBDataAPITester(api_key=args.test_archive)
        print("\n=== Testing Basic Archive ===")
        tester.test_archive_basic(year=args.year)

        print("\n\n=== Testing Filtered Archive (ACC) ===")
        tester.test_archive_with_filters(year=args.year, conf="ACC")

    elif args.test_dates:
        tester = CBBDataAPITester(api_key=args.test_dates)
        print("\n=== Testing Date Query Formats ===")
        results = tester.test_date_queries()
        print("\n\nResults Summary:")
        print(json.dumps(results, indent=2))

    elif args.save_sample:
        api_key, year = args.save_sample
        tester = CBBDataAPITester(api_key=api_key)
        tester.save_sample_data(int(year))

    else:
        parser.print_help()
        print("\n\nQuick Start:")
        print("  1. python test_cbbdata_api.py --login myuser mypass")
        print("  2. python test_cbbdata_api.py --test-archive YOUR_API_KEY")
        print("  3. python test_cbbdata_api.py --test-dates YOUR_API_KEY")


if __name__ == "__main__":
    main()
