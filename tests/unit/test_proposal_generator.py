"""Unit tests for ProposalGenerator + prompt/build helpers."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from needradar.models.proposal import ProjectProposal
from needradar.services.proposal_generator import (
    ProposalGenerator, _build_claude_prompt, _build_vault_body,
)


class TestBuildClaudePrompt:
    def test_includes_all_sections(self):
        @dataclass
        class R:
            title: str = "Test Project"
            problem_statement: str = "Users need X"
            target_user: str = "Developers"
            mvp_scope: list = None
            suggested_stack: dict = None
            effort_estimate: dict = None
            def __post_init__(self):
                if self.mvp_scope is None:
                    self.mvp_scope = []
                if self.suggested_stack is None:
                    self.suggested_stack = {}
                if self.effort_estimate is None:
                    self.effort_estimate = {}

        r = R(mvp_scope=[{"name": "Core", "priority": "P0", "description": "The core"}],
              suggested_stack={"frontend": "Vue 3", "backend": "FastAPI",
                               "database": "SQLite", "hosting": "Vercel",
                               "rationale": "Simple"})
        prompt = _build_claude_prompt(r)
        assert "Test Project" in prompt
        assert "Users need X" in prompt
        assert "P0" in prompt
        assert "Vue 3" in prompt


class TestBuildVaultBody:
    def test_includes_markdown(self):
        @dataclass
        class R:
            title: str = "P"
            problem_statement: str = "Problem"
            target_user: str = "Users"
            mvp_scope: list = None
            suggested_stack: dict = None
            effort_estimate: dict = None
            risks: list = None
            monetization_hint: str = ""
            def __post_init__(self):
                if self.mvp_scope is None:
                    self.mvp_scope = []
                if self.suggested_stack is None:
                    self.suggested_stack = {}
                if self.effort_estimate is None:
                    self.effort_estimate = {}
                if self.risks is None:
                    self.risks = []

        r = R(title="My Proposal")
        p = ProjectProposal(keyword="test", title="My Proposal")
        body = _build_vault_body(p, r)
        assert "My Proposal" in body


class TestProposalGenerator:
    @pytest.mark.asyncio
    async def test_generate_missing_opportunity(self, db_session):
        gen = ProposalGenerator(db_session)
        assert await gen.generate(99999) is None

    @pytest.mark.asyncio
    async def test_generate_missing_prompt(self, db_session):
        from needradar.models.opportunity import ProjectOpportunity
        opp = ProjectOpportunity(keyword="test", title="T", scores_json="{}",
                                 traction_json="[]", source_req_ids_json="[]")
        db_session.add(opp)
        await db_session.flush()

        with patch("needradar.services.proposal_generator._load_prompts", return_value={}):
            gen = ProposalGenerator(db_session)
            result = await gen.generate(opp.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_empty(self, db_session):
        gen = ProposalGenerator(db_session)
        rows, total = await gen.list_proposals()
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, db_session):
        gen = ProposalGenerator(db_session)
        assert await gen.get_proposal(99999) is None
