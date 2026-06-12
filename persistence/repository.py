import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from config import PERSISTENCE_PATH


class StockRepository:
    def __init__(
        self,
        path: str = PERSISTENCE_PATH
    ):
        self.path = Path(path)

    def save(self, records):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(records),
            "stocks": records
        }

        # Write to a temporary file and rename it into place so readers never
        # see a partially written snapshot.
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.path.parent,
            delete=False
        ) as temp_file:
            json.dump(
                payload,
                temp_file,
                indent=2,
                sort_keys=True
            )
            temp_file.write("\n")
            temp_path = Path(temp_file.name)

        temp_path.replace(
            self.path
        )

        return payload
