class LiveQuery:
    def query(self, entity_ref: str) -> dict:
        return {
            "entity_ref": entity_ref,
            "current_stage": "Proposal",
            "days_in_stage": 21,
            "deal_name": "Q3 Audit Engagement",
        }
