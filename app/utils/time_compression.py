"""
Time Compression Utilities for Development Testing

This module provides utilities to compress time intervals for E2E testing.
In production, workflows execute over days/weeks. For testing, we compress:
- 7 days → 7 minutes
- 1 day → 1 minute
- 1 hour → 1 second

This allows rapid validation of multi-day workflows without waiting for real-time execution.
"""

import os
from datetime import timedelta
from typing import Union


class TimeCompression:
    """Compress time intervals for development testing.

    Compression ratios (when enabled):
    - Days: 1 day = 1 minute (1440x speedup)
    - Hours: 1 hour = 1 second (3600x speedup)
    - Minutes: 1 minute = 1 second (60x speedup)

    Examples:
        # In production:
        wait_time = timedelta(days=7)  # 7 days

        # In testing:
        wait_time = TimeCompression.compress_timedelta(timedelta(days=7))  # 7 minutes

        # Or use individual methods:
        seconds = TimeCompression.compress_days(7)  # 420 seconds (7 minutes)
        seconds = TimeCompression.compress_hours(24)  # 24 seconds
        seconds = TimeCompression.compress_minutes(60)  # 60 seconds
    """

    # Compression is enabled by default for testing
    # Set DISABLE_TIME_COMPRESSION=true in .env to disable
    _enabled = os.getenv("DISABLE_TIME_COMPRESSION", "false").lower() != "true"

    # Compression ratios
    DAY_TO_MINUTE_RATIO = 1440  # 1 day = 1440 minutes → compress to 1 minute
    HOUR_TO_SECOND_RATIO = 3600  # 1 hour = 3600 seconds → compress to 1 second
    MINUTE_TO_SECOND_RATIO = 60  # 1 minute = 60 seconds → compress to 1 second

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if time compression is enabled."""
        return cls._enabled

    @classmethod
    def enable(cls):
        """Enable time compression (for testing)."""
        cls._enabled = True

    @classmethod
    def disable(cls):
        """Disable time compression (for production)."""
        cls._enabled = False

    @classmethod
    def compress_days(cls, days: float) -> float:
        """Convert days to compressed time in seconds.

        Args:
            days: Number of days

        Returns:
            Compressed time in seconds (1 day = 60 seconds when enabled)

        Examples:
            >>> TimeCompression.compress_days(7)  # 7 days
            420.0  # 7 minutes in seconds

            >>> TimeCompression.compress_days(1)  # 1 day
            60.0  # 1 minute in seconds
        """
        if not cls._enabled:
            return days * 24 * 3600  # Return actual seconds

        # 1 day → 1 minute = 60 seconds
        return days * 60

    @classmethod
    def compress_hours(cls, hours: float) -> float:
        """Convert hours to compressed time in seconds.

        Args:
            hours: Number of hours

        Returns:
            Compressed time in seconds (1 hour = 1 second when enabled)

        Examples:
            >>> TimeCompression.compress_hours(24)  # 24 hours
            24.0  # 24 seconds

            >>> TimeCompression.compress_hours(1)  # 1 hour
            1.0  # 1 second
        """
        if not cls._enabled:
            return hours * 3600  # Return actual seconds

        # 1 hour → 1 second
        return hours

    @classmethod
    def compress_minutes(cls, minutes: float) -> float:
        """Convert minutes to compressed time in seconds.

        Args:
            minutes: Number of minutes

        Returns:
            Compressed time in seconds (1 minute = 1 second when enabled)

        Examples:
            >>> TimeCompression.compress_minutes(30)  # 30 minutes
            30.0  # 30 seconds

            >>> TimeCompression.compress_minutes(5)  # 5 minutes
            5.0  # 5 seconds
        """
        if not cls._enabled:
            return minutes * 60  # Return actual seconds

        # 1 minute → 1 second
        return minutes

    @classmethod
    def compress_timedelta(cls, td: timedelta) -> timedelta:
        """Compress a timedelta object.

        Args:
            td: Original timedelta

        Returns:
            Compressed timedelta

        Examples:
            >>> TimeCompression.compress_timedelta(timedelta(days=7))
            timedelta(minutes=7)  # 7 days → 7 minutes

            >>> TimeCompression.compress_timedelta(timedelta(hours=24))
            timedelta(seconds=24)  # 24 hours → 24 seconds
        """
        if not cls._enabled:
            return td

        # Extract components
        days = td.days
        seconds = td.seconds

        # Convert to total seconds
        total_seconds = days * 24 * 3600 + seconds

        # Calculate compressed seconds
        # Break down into days, hours, minutes, seconds for compression
        days_component = days
        hours_component = seconds // 3600
        remaining_seconds = seconds % 3600
        minutes_component = remaining_seconds // 60
        seconds_component = remaining_seconds % 60

        # Compress each component
        compressed_seconds = (
            cls.compress_days(days_component) +
            cls.compress_hours(hours_component) +
            cls.compress_minutes(minutes_component) +
            seconds_component  # Seconds are not compressed further
        )

        return timedelta(seconds=compressed_seconds)

    @classmethod
    def compress_seconds(cls, seconds: float) -> float:
        """Compress a duration given in seconds.

        This method automatically detects the best compression ratio based on magnitude:
        - If >= 1 day (86400s): Use day compression
        - If >= 1 hour (3600s): Use hour compression
        - If >= 1 minute (60s): Use minute compression
        - Otherwise: No compression

        Args:
            seconds: Duration in seconds

        Returns:
            Compressed duration in seconds

        Examples:
            >>> TimeCompression.compress_seconds(86400)  # 1 day
            60.0  # 1 minute

            >>> TimeCompression.compress_seconds(3600)  # 1 hour
            1.0  # 1 second

            >>> TimeCompression.compress_seconds(300)  # 5 minutes
            5.0  # 5 seconds
        """
        if not cls._enabled:
            return seconds

        # Break down into components for appropriate compression
        days = seconds // 86400
        remaining = seconds % 86400

        hours = remaining // 3600
        remaining = remaining % 3600

        minutes = remaining // 60
        secs = remaining % 60

        # Compress each component
        return (
            cls.compress_days(days) +
            cls.compress_hours(hours) +
            cls.compress_minutes(minutes) +
            secs
        )

    @classmethod
    def format_compressed_time(cls, original_seconds: float) -> str:
        """Format compressed time for display.

        Args:
            original_seconds: Original duration in seconds

        Returns:
            Human-readable string showing original and compressed time

        Examples:
            >>> TimeCompression.format_compressed_time(86400)
            "1 day → 1 minute"

            >>> TimeCompression.format_compressed_time(3600)
            "1 hour → 1 second"
        """
        compressed = cls.compress_seconds(original_seconds)

        # Format original
        if original_seconds >= 86400:
            days = original_seconds // 86400
            orig_str = f"{days:.1f} day{'s' if days != 1 else ''}"
        elif original_seconds >= 3600:
            hours = original_seconds // 3600
            orig_str = f"{hours:.1f} hour{'s' if hours != 1 else ''}"
        elif original_seconds >= 60:
            minutes = original_seconds // 60
            orig_str = f"{minutes:.1f} minute{'s' if minutes != 1 else ''}"
        else:
            orig_str = f"{original_seconds:.1f} second{'s' if original_seconds != 1 else ''}"

        # Format compressed
        if compressed >= 60:
            minutes = compressed // 60
            comp_str = f"{minutes:.1f} minute{'s' if minutes != 1 else ''}"
        else:
            comp_str = f"{compressed:.1f} second{'s' if compressed != 1 else ''}"

        if cls._enabled:
            return f"{orig_str} → {comp_str}"
        else:
            return f"{orig_str} (no compression)"


# Convenience functions
def compress_days(days: float) -> float:
    """Compress days to seconds. See TimeCompression.compress_days()."""
    return TimeCompression.compress_days(days)


def compress_hours(hours: float) -> float:
    """Compress hours to seconds. See TimeCompression.compress_hours()."""
    return TimeCompression.compress_hours(hours)


def compress_minutes(minutes: float) -> float:
    """Compress minutes to seconds. See TimeCompression.compress_minutes()."""
    return TimeCompression.compress_minutes(minutes)


def compress_timedelta(td: timedelta) -> timedelta:
    """Compress a timedelta. See TimeCompression.compress_timedelta()."""
    return TimeCompression.compress_timedelta(td)


def compress_seconds(seconds: float) -> float:
    """Compress seconds. See TimeCompression.compress_seconds()."""
    return TimeCompression.compress_seconds(seconds)
