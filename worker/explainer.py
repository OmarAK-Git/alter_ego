import os
import json
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from core.database import SessionLocal
from core.models import DecisionRecordModel, ExplanationRecordModel, ProfileArtifactModel
from core.schemas.decisions import (
    DecisionRecord,
    ExplanationRecord,
    ClaimObject,
    CounterfactualEntry,
    ValidationStatus,
    ConfidenceLabel,
    FeatureContribution
)
from worker.scorer import load_scoring_config

import logging
logger = logging.getLogger(__name__)

PROHIBITED_TERMS = [
    "apt", "lazarus", "cozy bear", "fancy bear", "wannacry", "emotet", 
    "100% confidence", "certain", "proven beyond doubt", "undeniable proof"
]

def map_confidence_label(score: float) -> ConfidenceLabel:
    if score < 0.2:
        return ConfidenceLabel.very_low
    elif score < 0.4:
        return ConfidenceLabel.low
    elif score < 0.6:
        return ConfidenceLabel.moderate
    elif score < 0.8:
        return ConfidenceLabel.high
    else:
        return ConfidenceLabel.very_high

class LLMProvider:
    """Abstract interface for LLM calls."""
    def __init__(self):
        self.model_id = "stub-model-v1"
        
    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        """Override with actual LLM call."""
        raise NotImplementedError("Use a concrete provider")

class RealLLMProvider(LLMProvider):
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.provider_type = "anthropic"
            self.model_id = "claude-3-haiku-20240307"
        else:
            self.api_key = os.getenv("OPENAI_API_KEY")
            if self.api_key:
                self.provider_type = "openai"
                self.model_id = "gpt-4o-mini"
            else:
                self.provider_type = None
                self.model_id = "none"

    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        if not self.api_key:
            raise ValueError("No LLM API key configured in environment.")

        import requests

        if self.provider_type == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            data = {
                "model": self.model_id,
                "max_tokens": 1000,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]
            }
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            res_json = response.json()
            content_list = res_json.get("content", [])
            if content_list and isinstance(content_list, list):
                return content_list[0].get("text", "")
            raise ValueError("Invalid Anthropic API response format.")

        elif self.provider_type == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "content-type": "application/json"
            }
            data = {
                "model": self.model_id,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]
            }
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            res_json = response.json()
            choices = res_json.get("choices", [])
            if choices and isinstance(choices, list):
                return choices[0].get("message", {}).get("content", "")
            raise ValueError("Invalid OpenAI API response format.")

        else:
            raise ValueError("Unknown LLM provider configuration.")

class StubLLMProvider(LLMProvider):
    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        # A mock implementation returning JSON that matches the LLM output requirements
        # In a real environment, this calls the LLM API.
        try:
            # We will just parse the prompt vaguely or return a valid stub
            return json.dumps({
                "summary_text": "The event deviated significantly from the entity's baseline.",
                "claim_objects": [] # we rely on template fallback if claims are empty or we can fake it
            })
        except Exception:
            return "{}"

def build_prompt(decision: DecisionRecordModel, profile, config: Dict[str, Any]) -> str:
    context = {
        "decision_id": decision.decision_id,
        "score": decision.score,
        "confidence": decision.confidence,
        "contributions": decision.contributions,
        "profile_features": profile.features if profile else {}
    }
    
    prompt = f"""
    You are an analyst explainer. Explain this behavioral anomaly.
    Do NOT use threat actor names or specific malware names.
    Return a JSON object with:
    - summary_text (str)
    - claim_objects (list of dicts with 'contribution_id' and 'claim_text' and 'evidence_binding' (list of contribution_ids))
    
    Context:
    <context>
    {json.dumps(context, indent=2)}
    </context>
    """
    return prompt

def generate_template_explanation(decision: DecisionRecordModel, top_k_cf: List[CounterfactualEntry]) -> ExplanationRecord:
    prompt_hash = hashlib.sha256(b"template_fallback").hexdigest()
    response_hash = hashlib.sha256(b"template_fallback").hexdigest()
    
    claims = []
    conts = decision.contributions
    if not isinstance(conts, list):
        conts = []
        
    for c in sorted(conts, key=lambda x: x.get('contribution_score', 0), reverse=True)[:3]:
        cid = c.get('contribution_id', '')
        cname = c.get('feature_name', '')
        cscore = c.get('contribution_score', 0.0)
        cweight = c.get('confidence_weight', 0.0)
        claims.append(ClaimObject(
            contribution_id=cid,
            claim_text=f"The feature {cname} contributed {cscore:.2f} to the score.",
            evidence_binding=[cid],
            confidence_label=map_confidence_label(cweight)
        ))
        
    return ExplanationRecord(
        decision_id=decision.decision_id,
        summary_text="This explanation was generated via template fallback.",
        claim_objects=claims,
        counterfactuals=top_k_cf,
        validation_status=ValidationStatus.template_fallback,
        validation_notes="Template fallback executed.",
        llm_model_id="template-v1",
        prompt_hash=prompt_hash,
        response_hash=response_hash,
        created_at=datetime.utcnow()
    )

def check_prohibited_content(text: str) -> bool:
    low = text.lower()
    for term in PROHIBITED_TERMS:
        if term in low:
            return True
    return False

def generate_explanation(decision_id: str, db: Session = None, provider: LLMProvider = None) -> ExplanationRecord:
    if db is None:
        db = SessionLocal()
        
    decision = db.query(DecisionRecordModel).filter(DecisionRecordModel.decision_id == decision_id).first()
    if not decision:
        raise ValueError(f"Decision {decision_id} not found")
        
    profile = db.query(ProfileArtifactModel).filter(ProfileArtifactModel.profile_version == decision.profile_version).first()
    # Profile may be missing for replayed or synthetic decisions — template fallback handles it gracefully
    config = load_scoring_config()
    
    if provider is None:
        provider = RealLLMProvider()
        
    # Build deterministic top-K counterfactuals
    conts = decision.contributions
    if not isinstance(conts, list):
        conts = []
    
    sorted_conts = sorted(conts, key=lambda x: x.get("contribution_score", 0.0), reverse=True)
    top_k_cf = []
    for c in sorted_conts[:3]:
        cid = c.get("contribution_id", "")
        cname = c.get("feature_name", "")
        cscore = c.get("contribution_score", 0.0)
        cf_text = f"If {cname} had been within typical range, the score would have been {cscore:.2f} lower."
        top_k_cf.append(CounterfactualEntry(
            contribution_id=cid,
            counterfactual_text=cf_text,
            score_delta=cscore
        ))
        
    prompt = build_prompt(decision, profile, config)  # profile may be None → template handles it
    prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
    
    try:
        raw_response = provider.generate(prompt)
        response_hash = hashlib.sha256(raw_response.encode('utf-8')).hexdigest()
        
        # Clean markdown code blocks if the LLM wrapped it in ```json ... ```
        clean_response = raw_response.strip()
        if clean_response.startswith("```"):
            lines = clean_response.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_response = "\n".join(lines).strip()
            
        parsed = json.loads(clean_response)
        summary = parsed.get("summary_text", "")
        raw_claims = parsed.get("claim_objects", [])
        
        if check_prohibited_content(summary):
            raise ValueError("Prohibited content in summary")
            
        valid_claims = []
        valid_contribution_ids = {c.get("contribution_id") for c in conts}
        
        for rc in raw_claims:
            if check_prohibited_content(rc.get("claim_text", "")):
                raise ValueError("Prohibited content in claim")
                
            cid = rc.get("contribution_id")
            if cid not in valid_contribution_ids:
                raise ValueError(f"Invalid contribution ID binding: {cid}")
                
            bindings = rc.get("evidence_binding", [])
            for b in bindings:
                if b not in valid_contribution_ids:
                    raise ValueError(f"Invalid evidence binding: {b}")
            
            # Find confidence
            orig_cont = next((c for c in conts if c.get("contribution_id") == cid), None)
            cweight = orig_cont.get("confidence_weight", 0.0) if orig_cont else 0.0
            
            valid_claims.append(ClaimObject(
                contribution_id=cid,
                claim_text=rc.get("claim_text", ""),
                evidence_binding=bindings,
                confidence_label=map_confidence_label(cweight)
            ))
            
        if not summary or not valid_claims:
            raise ValueError("Empty summary or claims")

        record = ExplanationRecord(
            decision_id=decision.decision_id,
            summary_text=summary,
            claim_objects=valid_claims,
            counterfactuals=top_k_cf,
            validation_status=ValidationStatus.passed,
            validation_notes=None,
            llm_model_id=provider.model_id,
            prompt_hash=prompt_hash,
            response_hash=response_hash,
            created_at=datetime.utcnow()
        )
    except Exception as e:
        logger.warning(f"LLM explanation failed validation, using template. Reason: {e}")
        record = generate_template_explanation(decision, top_k_cf)
        record.validation_notes = str(e)
        
    # Save to DB
    db_record = ExplanationRecordModel(
        decision_id=record.decision_id,
        summary_text=record.summary_text,
        claim_objects=[c.model_dump() for c in record.claim_objects],
        counterfactuals=[c.model_dump() for c in record.counterfactuals],
        validation_status=record.validation_status.value,
        validation_notes=record.validation_notes,
        llm_model_id=record.llm_model_id,
        prompt_hash=record.prompt_hash,
        response_hash=record.response_hash,
        created_at=record.created_at
    )
    # Use merge to handle replays gracefully
    db.merge(db_record)
    db.commit()
    
    return record
