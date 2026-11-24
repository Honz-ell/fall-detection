"""Shared configuration for the local demo APIs."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv(
    "FALL_POSTGRES_URL",
    "postgresql://falld:fall_dev_password@localhost:5434/falldetect",
)


def connect():
    return psycopg.connect(DATABASE_URL, connect_timeout=5)
