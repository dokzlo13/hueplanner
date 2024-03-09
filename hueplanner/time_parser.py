from __future__ import annotations

import re
from datetime import datetime, timedelta

from zoneinfo import ZoneInfo

from hueplanner.storage.interface import IKeyValueCollection


class TimeParser:
    def __init__(self, tz: ZoneInfo, storage: IKeyValueCollection):
        self.tz = tz
        self.storage = storage

    async def parse(self, input_time):
        # Match @variable pattern
        variable_match = re.match(r"@(\w+)", input_time)
        if variable_match:
            var_name = variable_match.group(1)
            if var_name == "now":  # hack to allow "@now" time
                base_time = datetime.now(tz=self.tz)
            else:
                base_time = await self.storage.get(var_name)
            if base_time:
                # Check for modifier after @variable
                modifier_match = re.search(r"([-+])\s*(\d+H)?(\d+M)?", input_time, re.IGNORECASE)
                if modifier_match:
                    return self.apply_modifier(base_time, modifier_match)
                return base_time
            else:
                raise ValueError(f"Time variable '@{var_name}' is not defined.")

        # Match XX:XX pattern for exact time
        time_match = re.match(r"(\d{1,2}):(\d{2})", input_time)
        if time_match:
            hours, minutes = time_match.groups()
            base_time = datetime.now().replace(hour=int(hours), minute=int(minutes), second=0, microsecond=0)

            # Check for time modifiers (+/- HH:MM or HHhMMm...)
            modifier_match = re.search(r"([-+])\s*(\d+H)?(\d+M)?", input_time, re.IGNORECASE)
            if modifier_match:
                return self.apply_modifier(base_time, modifier_match)

            return base_time

        raise ValueError(f"Input time {input_time} is not recognized.")

    def apply_modifier(self, base_time, modifier_match):
        """Applies time modifier to base_time."""
        sign, hour_mod, minute_mod = modifier_match.groups()
        hours_delta = int(hour_mod[:-1]) if hour_mod else 0
        minutes_delta = int(minute_mod[:-1]) if minute_mod else 0
        if sign == "-":
            hours_delta *= -1
            minutes_delta *= -1
        return base_time + timedelta(hours=hours_delta, minutes=minutes_delta)


# Unit test for UpdatedTimeParser
def test_time_parser():
    variables = {
        "dawn": datetime(2023, 1, 1, 6, 0),
        "noon": datetime(2023, 1, 1, 12, 0),
        "midnight": datetime(2023, 1, 1, 0, 0),
    }
    parser = TimeParser(variables)

    assert parser.parse("@dawn") == datetime(2023, 1, 1, 6, 0), "Variable parsing failed"
    assert parser.parse("13:00") == datetime.now().replace(
        hour=13, minute=0, second=0, microsecond=0
    ), "Exact time parsing failed"
    assert parser.parse("12:00 + 40M") == datetime.now().replace(
        hour=12, minute=40, second=0, microsecond=0
    ), "Positive minute modifier parsing failed"
    assert parser.parse("@noon - 20M") == datetime(
        2023, 1, 1, 11, 40
    ), "Negative minute modifier parsing failed at @variable"
    assert parser.parse("@midnight + 10M") == datetime(
        2023, 1, 1, 0, 10
    ), "Positive minute modifier parsing failed at @variable"

    print("All tests passed!")


if __name__ == "__main__":
    test_time_parser()
