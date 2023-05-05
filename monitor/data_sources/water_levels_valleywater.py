import requests

from typing import List, Dict
from . import DataSource
from datetime import datetime, timezone
from urllib.parse import urljoin


class valleywater(DataSource):
    base_url = "https://alertdata.valleywater.org/"

    def load_water_stations(self) -> dict:
        results = self.get_cached_results()

        if results is None:
            resp = requests.get(urljoin(self.base_url, "/Sensor/current"))
            results = resp.json()["streams"]
            self.save_cached_results(results)

        return results

    def get_water_stations(self, watershed=None, station_ids=None) -> List[Dict]:
        all_stations = self.load_water_stations()

        if watershed is None:
            watershed = getattr(self, "watershed", None)

        if station_ids is None:
            station_ids = getattr(self, "station_ids", None)

        stations = []
        for station in all_stations:
            # If the station was last updated over 24 hours ago, skip it.
            if (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(station["timestamp"])
            ).total_seconds() > 60 * 60 * 24:
                continue

            if watershed is None and station_ids is None:
                stations.append(station)

            if station_ids is not None:
                if station["gageId"] in station_ids:
                    stations.append(station)
            if watershed is not None:
                if station["watershed"] == watershed:
                    stations.append(station)

        return stations

    def get_water_stations_above_threshold(
        self, watershed=None, station_ids=None, above_threshold=1
    ) -> List[Dict]:
        water_severity = {
            0: "Normal",
            1: "Take Action",
            2: "Minor Flooding",
            3: "Moderate Flooding",
            4: "Major Flooding",
        }

        stations = self.get_water_stations(watershed=watershed, station_ids=station_ids)

        stations_above_threshold = []
        for station in stations:
            is_above_threshold = False
            for threshold in range(above_threshold, 5):
                rated_key = f"th{threshold}_rated"
                direct_key = f"th{threshold}_direct"
                threshold_description_key = f"threshold{threshold}Desc"

                if (
                    station[rated_key] != 0 and station["flow"] > station[rated_key]
                ) or (
                    station[direct_key] != 0 and station["stage"] > station[direct_key]
                ):
                    extras = {
                        "severity_label": water_severity[threshold],
                        "expected_conditions": station[threshold_description_key],
                    }
                    is_above_threshold = True

            if is_above_threshold:
                station.update(extras)
                stations_above_threshold.append(station)

        return stations_above_threshold

    def get_status(self) -> Dict:
        water_stations = self.get_water_stations_above_threshold()

        alerts = []
        if water_stations:
            message = "ALERT!! The following water level readings are above threshold levels:\n"

            for station in water_stations:
                message += f"  Name: {station['name']}\n"
                message += f"  Watershed: {station['watershed']}\n"
                message += f"  Status: {station['severity_label']}\n"
                message += (
                    f"  Expected conditions: {station['expected_conditions']}\n\n"
                )
                alerts.append(station)
        else:
            message = "Water levels normal."

        return {
            "message": message,
            "alerts": alerts,
        }


# Used only for testing
if __name__ == "__main__":
    air_monitor = valleywater(
        watershed="Guadalupe",
    )
    print(air_monitor.get_status()["message"])
