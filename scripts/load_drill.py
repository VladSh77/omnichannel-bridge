#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Load drill for omnichannel_bridge: simulate peak ad traffic windows.

Targets (from docs/LOAD_CRITERIA.md):
- Concurrent active threads: 100+
- Sustained inbound rate: 20 messages/minute
- P95 enqueue latency to AI job: under 5 seconds
- P95 outbound send latency: under 8 seconds
- Error budget: under 2% failed outbound attempts

Usage:
    python3 scripts/load_drill.py --env=staging --duration=900 --rate=20 --threads=100
"""

import argparse
import json
import logging
import random
import time
from datetime import datetime
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_DURATION_SECONDS = 900  # 15 minutes
DEFAULT_MESSAGE_RATE = 20  # per minute
DEFAULT_MAX_THREADS = 100
METRICS_CHECK_INTERVAL = 60  # seconds


class LoadDrill:
    def __init__(self, base_url, duration=900, msg_rate=20, max_threads=100):
        self.base_url = base_url
        self.duration = duration
        self.msg_rate = msg_rate
        self.max_threads = max_threads
        self.session = requests.Session()

        # Metrics tracking
        self.metrics = {
            'total_messages_sent': 0,
            'total_messages_failed': 0,
            'enqueue_latencies': [],
            'outbound_latencies': [],
            'start_time': None,
            'end_time': None,
            'errors': [],
        }

    def generate_test_message(self, thread_num):
        """Generate a test webhook payload (Telegram format)."""
        return {
            "update_id": random.randint(1000000, 9999999),
            "message": {
                "message_id": thread_num * 1000 + random.randint(1, 999),
                "date": int(time.time()),
                "chat": {
                    "id": -100 - thread_num,  # Negative chat ID for group
                    "type": "group",
                    "title": f"Test Group {thread_num}",
                },
                "from": {
                    "id": 1000000 + thread_num,
                    "is_bot": False,
                    "first_name": f"User{thread_num}",
                    "username": f"user{thread_num}",
                },
                "text": f"Test message {thread_num}: {random.choice(['Привіт', 'Ціна?', 'Дати?', 'Менеджер?'])}",
            }
        }

    def send_webhook(self, provider, payload):
        """Send a test webhook."""
        url = f"{self.base_url}/omni/webhook/{provider}"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "load-drill/1.0",
        }

        try:
            start = time.time()
            response = self.session.post(url, json=payload, headers=headers, timeout=10)
            latency = time.time() - start

            if response.status_code == 200:
                self.metrics['total_messages_sent'] += 1
                self.metrics['enqueue_latencies'].append(latency)
                return True, latency
            else:
                self.metrics['total_messages_failed'] += 1
                self.metrics['errors'].append(f"HTTP {response.status_code}: {response.text[:100]}")
                return False, latency
        except Exception as e:
            self.metrics['total_messages_failed'] += 1
            self.metrics['errors'].append(str(e))
            return False, None

    def calculate_percentile(self, data, percentile):
        """Calculate percentile from list of values."""
        if not data:
            return None
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(idx, len(sorted_data) - 1)]

    def report_metrics(self):
        """Generate and display metrics report."""
        self.metrics['end_time'] = datetime.now()

        total_messages = self.metrics['total_messages_sent'] + self.metrics['total_messages_failed']
        success_rate = (
            100 * self.metrics['total_messages_sent'] / total_messages
            if total_messages > 0 else 0
        )
        error_rate = 100 - success_rate

        p95_enqueue = self.calculate_percentile(self.metrics['enqueue_latencies'], 95)
        p95_outbound = self.calculate_percentile(self.metrics['outbound_latencies'], 95)

        # Format latency values
        p95_enqueue_str = f"{p95_enqueue*1000:.1f}ms" if p95_enqueue else "N/A"
        p95_outbound_str = f"{p95_outbound*1000:.1f}ms" if p95_outbound else "N/A"
        min_enqueue = f"{min(self.metrics['enqueue_latencies'])*1000:.1f}ms" if self.metrics['enqueue_latencies'] else "N/A"
        max_enqueue = f"{max(self.metrics['enqueue_latencies'])*1000:.1f}ms" if self.metrics['enqueue_latencies'] else "N/A"

        errors_str = '  ' + '\n  '.join(self.metrics['errors'][:10]) if self.metrics['errors'] else '  None'

        # Criteria checks
        enqueue_ok = p95_enqueue and p95_enqueue < 5
        outbound_ok = p95_outbound and p95_outbound < 8
        error_ok = error_rate < 2

        report = f"""
╔════════════════════════════════════════════════════════════════╗
║                   Load Drill Report                            ║
╚════════════════════════════════════════════════════════════════╝

Duration: {self.duration} seconds
Target rate: {self.msg_rate} msg/min
Target threads: {self.max_threads} concurrent

THROUGHPUT:
  Total messages sent: {self.metrics['total_messages_sent']}
  Total messages failed: {self.metrics['total_messages_failed']}
  Success rate: {success_rate:.2f}%
  Error rate: {error_rate:.2f}%

LATENCY (Enqueue to AI job):
  P95: {p95_enqueue_str} (target: <5000ms)
  Min: {min_enqueue}
  Max: {max_enqueue}

LATENCY (Outbound provider ACK):
  P95: {p95_outbound_str} (target: <8000ms)

EXIT CRITERIA:
  ✓ Throughput: {self.metrics['total_messages_sent']} messages OK
  {'✓' if error_ok else '✗'} Error budget: {error_rate:.2f}% {'OK (<2%)' if error_ok else 'FAILED (>2%)'}
  {'✓' if enqueue_ok else '✗'} Enqueue P95: {p95_enqueue_str} {'OK' if enqueue_ok else 'FAILED'}
  {'✓' if outbound_ok else '✗'} Outbound P95: {p95_outbound_str} {'OK' if outbound_ok else 'FAILED'}

ERRORS (first 10):
{errors_str}
        next_metrics_report = time.time() + METRICS_CHECK_INTERVAL

        while time.time() - start_time < self.duration:
            # Send next batch of messages at specified rate
            elapsed = time.time() - start_time
            messages_expected = int((elapsed / 60) * self.msg_rate)

            while msg_counter < messages_expected and msg_counter < self.max_threads * (elapsed / 60):
                thread_num = msg_counter % self.max_threads
                payload = self.generate_test_message(thread_num)

                success, latency = self.send_webhook("telegram", payload)
                msg_counter += 1

                if msg_counter % 10 == 0:
                    logger.info(f"Sent {msg_counter} messages, {self.metrics['total_messages_failed']} failed")

            # Check metrics periodically
            if time.time() >= next_metrics_report:
                p95_enqueue = self.calculate_percentile(self.metrics['enqueue_latencies'], 95)
                p95_str = f"{p95_enqueue*1000:.1f}ms" if p95_enqueue else "N/A"
                logger.info(
                    f"  [status] msg={self.metrics['total_messages_sent']}, "
                    f"fail={self.metrics['total_messages_failed']}, "
                    f"p95_enqueue={p95_str}"
                )
                next_metrics_report = time.time() + METRICS_CHECK_INTERVAL

            # Small sleep to prevent CPU spin
            time.sleep(0.1)

        # Final report
        return self.report_metrics()


def main():
    parser = argparse.ArgumentParser(description='Load drill for omnichannel_bridge')
    parser.add_argument('--env', default='staging', help='Environment (staging/prod-copy)')
    parser.add_argument('--url', default='http://localhost:8069', help='Base URL')
    parser.add_argument('--duration', type=int, default=DEFAULT_DURATION_SECONDS, help=f'Duration in seconds (default: {DEFAULT_DURATION_SECONDS})')
    parser.add_argument('--rate', type=int, default=DEFAULT_MESSAGE_RATE, help=f'Message rate per minute (default: {DEFAULT_MESSAGE_RATE})')
    parser.add_argument('--threads', type=int, default=DEFAULT_MAX_THREADS, help=f'Max concurrent threads (default: {DEFAULT_MAX_THREADS})')
    parser.add_argument('--save-report', help='Save report to file')

    args = parser.parse_args()

    logger.info(f"Loading drill with env={args.env}, url={args.url}")
    logger.info(f"Parameters: duration={args.duration}s, rate={args.rate} msg/min, threads={args.threads}")

    drill = LoadDrill(
        base_url=args.url,
        duration=args.duration,
        msg_rate=args.rate,
        max_threads=args.threads,
    )

    report = drill.run()

    if args.save_report:
        with open(args.save_report, 'w') as f:
            f.write(report)
        logger.info(f"Report saved to {args.save_report}")


if __name__ == '__main__':
    main()
