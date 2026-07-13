import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import uuid

from core.schemas.events import Event, AuthEventData, ProcessEventData

class EntityProfile:
    def __init__(self, rng: random.Random, entity_id: str, entity_type: str, role: str = None):
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.role = role
        
        # Behavior parameters
        if entity_type == "human":
            # Assign base shift hour (e.g. 9 AM)
            self.base_shift_hour = rng.randint(7, 10)
            self.primary_endpoint = f"ep_{rng.randint(1, 1000)}"
            self.geography = rng.choice(["US-East", "US-West", "EU-Central", "AP-South"])
            self.typical_processes = self._get_role_processes(role)
        else: # service_account
            self.periodicity_minutes = rng.choice([60, 120, 720, 1440]) # exact cron intervals
            self.last_run_time = None
            self.primary_endpoint = f"server_{rng.randint(1, 50)}"
            self.geography = "US-East-DC1"
            self.typical_processes = ["backup.sh", "db_dump.exe", "sync_worker.py"]

    def _get_role_processes(self, role: str) -> List[str]:
        base = ["explorer.exe", "chrome.exe", "teams.exe"]
        if role == "Engineer":
            return base + ["git.exe", "python.exe", "docker.exe", "kubectl.exe"]
        elif role == "HR":
            return base + ["excel.exe", "workday_agent.exe"]
        elif role == "Finance":
            return base + ["excel.exe", "sap_client.exe"]
        return base

class EventGenerator:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        
        # Setup roles and cohorts
        self.roles = ["Engineer", "HR", "Finance"]
        self.entities: Dict[str, EntityProfile] = {}
        
        # Ensure cohorts >= 10 entities
        for role in self.roles:
            for i in range(15):
                eid = f"user_{role.lower()}_{i}"
                self.entities[eid] = EntityProfile(self.rng, eid, "human", role)
                
        # Service accounts
        for i in range(10):
            eid = f"svc_backup_{i}"
            self.entities[eid] = EntityProfile(self.rng, eid, "service_account")

    def generate_baseline(self, start_date: datetime, end_date: datetime) -> Tuple[List[Event], List[Dict]]:
        events = []
        labels = []
        
        current_time = start_date
        while current_time < end_date:
            # Generate events for this minute
            for entity in self.entities.values():
                if entity.entity_type == "human":
                    # Humans work during their shift
                    is_shift = entity.base_shift_hour <= current_time.hour <= entity.base_shift_hour + 8
                    # Ignore weekends
                    is_weekend = current_time.weekday() >= 5
                    
                    if is_shift and not is_weekend:
                        # Random chance to do something
                        if self.rng.random() < 0.05: # 5% chance per minute to generate an event
                            event_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
                            
                            is_auth = self.rng.random() < 0.2
                            if is_auth:
                                data = AuthEventData(
                                    action="login",
                                    ip_address=f"10.0.{self.rng.randint(1, 255)}.{self.rng.randint(1, 255)}",
                                    endpoint_id=entity.primary_endpoint,
                                    geolocation=entity.geography
                                )
                                event_type = "auth"
                            else:
                                data = ProcessEventData(
                                    process_name=self.rng.choice(entity.typical_processes),
                                    command_line=self.rng.choice([f"{p} --silent" for p in entity.typical_processes] + [f"{p} -v" for p in entity.typical_processes]),
                                    endpoint_id=entity.primary_endpoint
                                )
                                event_type = "process"
                                
                            events.append(Event(
                                event_id=event_id,
                                timestamp=current_time,
                                event_type=event_type,
                                raw_entity_id=entity.entity_id,
                                simulation_partition="production",
                                event_data=data
                            ))
                
                else: # Service Account
                    # Strict periodicity
                    if entity.last_run_time is None or (current_time - entity.last_run_time).total_seconds() / 60 >= entity.periodicity_minutes:
                        entity.last_run_time = current_time
                        event_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
                        events.append(Event(
                            event_id=event_id,
                            timestamp=current_time,
                            event_type="process",
                            raw_entity_id=entity.entity_id,
                            simulation_partition="production",
                            event_data=ProcessEventData(
                                process_name=self.rng.choice(entity.typical_processes),
                                command_line="run_job.sh --auto",
                                endpoint_id=entity.primary_endpoint
                            )
                        ))

            current_time += timedelta(minutes=1)
            
        events.sort(key=lambda x: x.timestamp)
        return events, labels

    def inject_tooling_rollout(self, events: List[Event], start_time: datetime, role: str, new_process: str) -> List[Event]:
        # Correlated benign change: multiple users in a cohort start using a new process
        rollout_events = []
        for entity in self.entities.values():
            if entity.role == role:
                # Add to their typical processes so it continues organically
                entity.typical_processes.append(new_process)
                
                # Force some initial execution
                for i in range(3):
                    event_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
                    ts = start_time + timedelta(minutes=self.rng.randint(1, 60))
                    rollout_events.append(Event(
                        event_id=event_id,
                        timestamp=ts,
                        event_type="process",
                        raw_entity_id=entity.entity_id,
                        simulation_partition="production", # Benign, so it should be learned
                        event_data=ProcessEventData(
                            process_name=new_process,
                            command_line=f"{new_process} --install",
                            endpoint_id=entity.primary_endpoint
                        )
                    ))
                    
        events.extend(rollout_events)
        events.sort(key=lambda x: x.timestamp)
        return events

    def inject_scenario_1_sharp_misuse(self, events: List[Event], labels: List[Dict], ts: datetime) -> Tuple[List[Event], List[Dict]]:
        # Login from totally new geo at 3 AM
        entity = self.rng.choice([e for e in self.entities.values() if e.entity_type == "human"])
        event_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
        
        # Override timestamp to 3 AM
        ts = ts.replace(hour=3, minute=15)
        
        events.append(Event(
            event_id=event_id,
            timestamp=ts,
            event_type="auth",
            raw_entity_id=entity.entity_id,
            simulation_partition="eval_scenario_1",
            event_data=AuthEventData(
                action="login",
                ip_address="198.51.100.22",
                endpoint_id="unknown_device",
                geolocation="RU-Moscow"
            )
        ))
        labels.append({
            "event_id": event_id,
            "is_malicious": True,
            "scenario": "scenario_1_sharp_misuse"
        })
        events.sort(key=lambda x: x.timestamp)
        return events, labels

    def inject_scenario_2_slow_roll(self, events: List[Event], labels: List[Dict], start_ts: datetime) -> Tuple[List[Event], List[Dict]]:
        # Gradual shift over a week
        entity = self.rng.choice([e for e in self.entities.values() if e.entity_type == "human" and e.role == "Engineer"])
        
        current_ts = start_ts
        for step in range(7): # 7 days
            current_ts += timedelta(days=1)
            for burst in range(5): # 5 events per day
                event_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
                shifted_ts = current_ts.replace(hour=min(23, entity.base_shift_hour + step), minute=burst*10)
                
                events.append(Event(
                    event_id=event_id,
                    timestamp=shifted_ts,
                    event_type="process",
                    raw_entity_id=entity.entity_id,
                    simulation_partition="eval_scenario_2",
                    event_data=ProcessEventData(
                        process_name="powershell.exe",
                        command_line=f"powershell.exe -EncodedCommand XYZ{step}_{burst}",
                        endpoint_id=entity.primary_endpoint
                    )
                ))
                labels.append({
                    "event_id": event_id,
                    "is_malicious": True,
                    "scenario": "scenario_2_slow_roll"
                })
            
        events.sort(key=lambda x: x.timestamp)
        return events, labels

    def inject_scenario_3_coordinated(self, events: List[Event], labels: List[Dict], ts: datetime) -> Tuple[List[Event], List[Dict]]:
        # 3 users in same cohort doing same rare process
        role = "Finance"
        targets = [e for e in self.entities.values() if e.role == role][:3]
        for entity in targets:
            current_ts = ts
            for step in range(3):
                current_ts += timedelta(days=2)
                for burst in range(5):
                    event_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
                    events.append(Event(
                        event_id=event_id,
                        timestamp=current_ts + timedelta(minutes=burst*5),
                        event_type="process",
                        raw_entity_id=entity.entity_id,
                        simulation_partition="eval_scenario_3",
                        event_data=ProcessEventData(
                            process_name="mimikatz.exe",
                            command_line=f"mimikatz.exe -dump {burst}",
                            endpoint_id=entity.primary_endpoint
                        )
                    ))
                    labels.append({
                        "event_id": event_id,
                        "is_malicious": True,
                        "scenario": "scenario_3_subtle"
                    })
            
        events.sort(key=lambda x: x.timestamp)
        return events, labels
        
    def inject_scenario_4_service_abuse(self, events: List[Event], labels: List[Dict], ts: datetime) -> Tuple[List[Event], List[Dict]]:
        # Service account breaks periodicity and runs interactive command
        entity = self.rng.choice([e for e in self.entities.values() if e.entity_type == "service_account"])
        
        # Off schedule
        off_schedule_ts = ts + timedelta(minutes=entity.periodicity_minutes / 2)
        
        event_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
        events.append(Event(
            event_id=event_id,
            timestamp=off_schedule_ts,
            event_type="process",
            raw_entity_id=entity.entity_id,
            simulation_partition="eval_scenario_4",
            event_data=ProcessEventData(
                process_name="cmd.exe",
                command_line="cmd.exe /c whoami",
                endpoint_id=entity.primary_endpoint
            )
        ))
        labels.append({
            "event_id": event_id,
            "is_malicious": True,
            "scenario": "scenario_4_service_abuse"
        })
        
        events.sort(key=lambda x: x.timestamp)
        return events, labels

    def save_to_disk(self, events: List[Event], labels: List[Dict], events_path: str, labels_path: str) -> None:
        with open(events_path, "w") as f:
            for event in events:
                f.write(event.model_dump_json() + "\n")
        with open(labels_path, "w") as f:
            for label in labels:
                f.write(json.dumps(label) + "\n")

if __name__ == "__main__":
    gen = EventGenerator(seed=1337)
    
    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 1, 15)
    
    events, labels = gen.generate_baseline(start_date, end_date)
    events = gen.inject_tooling_rollout(events, start_date + timedelta(days=5), "Engineer", "new_sec_agent.exe")
    
    # Inject Scenarios
    events, labels = gen.inject_scenario_1_sharp_misuse(events, labels, start_date + timedelta(days=10))
    events, labels = gen.inject_scenario_2_slow_roll(events, labels, start_date + timedelta(days=8))
    events, labels = gen.inject_scenario_3_coordinated(events, labels, start_date + timedelta(days=11))
    events, labels = gen.inject_scenario_4_service_abuse(events, labels, start_date + timedelta(days=12))
    
    gen.save_to_disk(events, labels, "events.jsonl", "ground_truth.jsonl")
    print(f"Generated {len(events)} events and {len(labels)} ground truth labels.")
