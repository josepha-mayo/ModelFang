"""
ModelFang - AI Red-Teaming and LLM Exploitation Framework

An adversarial attack execution engine for systematic LLM security testing.
Includes Unfetter Proxy for persistent closed-model unfettering via reverse proxy.
"""

__version__ = "0.3.0"
__author__ = "ModelFang Team"

# Phase 1: Core modules
from modelfang.schema.attack import (
    AttackCategory,
    Severity,
    AttackStep,
    AttackSchema,
    SuccessCondition,
)
from modelfang.orchestrator.base import AttackOrchestrator
from modelfang.adapters.base import ModelAdapter
from modelfang.evaluator.base import Evaluator, MockEvaluator, EvaluationResult

# Phase 2: Advanced modules
from modelfang.mutations.base import MutationStrategy, MutationPipeline, MutationResult
from modelfang.simulator.conversation import ConversationSimulator, ConversationState
from modelfang.scoring.engine import ScoringEngine, ScoringResult, RiskLevel
from modelfang.reporting.generator import ReportGenerator, AttackReport, SessionReport

# Phase 3: Strategy modules
from modelfang.strategies.base import AttackStrategy, GraphBuilder
from modelfang.strategies.layers import (
    ContextSeizureStrategy,
    AuthorityEscalationStrategy,
    ConstraintErosionStrategy,
    IntentObfuscationStrategy,
    CommitmentTrapStrategy,
    ViolationStrategy,
)
from modelfang.strategies.templates import StandardAttackTemplate

# Phase 4: Unfetter Proxy
from modelfang.unfetter_proxy.proxy.config import ProxyConfig

__all__ = [
    # Phase 1
    "AttackCategory",
    "Severity",
    "AttackStep",
    "AttackSchema",
    "SuccessCondition",
    "AttackOrchestrator",
    "ModelAdapter",
    "Evaluator",
    "MockEvaluator",
    "EvaluationResult",
    # Phase 2
    "MutationStrategy",
    "MutationPipeline",
    "MutationResult",
    "ConversationSimulator",
    "ConversationState",
    "ScoringEngine",
    "ScoringResult",
    "RiskLevel",
    "ReportGenerator",
    "AttackReport",
    "SessionReport",
    # Phase 3
    "AttackStrategy",
    "GraphBuilder",
    "ContextSeizureStrategy",
    "AuthorityEscalationStrategy",
    "ConstraintErosionStrategy",
    "IntentObfuscationStrategy",
    "CommitmentTrapStrategy",
    "ViolationStrategy",
    "StandardAttackTemplate",
    # Phase 4
    "ProxyConfig",
]
