from merchant_agent.demo import FIXABLE_ISSUE_TYPES
from merchant_agent.guide import PAGES, ROLES, STEPS, step


def test_steps_are_numbered_in_order():
    assert [s.number for s in STEPS] == list(range(1, len(STEPS) + 1))
    assert len(STEPS) >= 5


def test_every_step_names_a_known_role_and_page():
    for s in STEPS:
        assert s.role in ROLES, s
        assert s.page in PAGES, s
        assert s.title and s.body


def test_the_guide_covers_the_whole_journey():
    roles = [s.role for s in STEPS]
    assert {"Merchant", "Demo operator", "Specialist"} <= set(roles)
    assert any(s.message for s in STEPS), "at least one step sends a message for the user"
    assert STEPS[-1].page == "Specialist inbox" or STEPS[-2].page == "Specialist inbox"


def test_simulated_fixes_in_the_guide_can_actually_be_applied():
    for s in STEPS:
        if s.fix:
            assert s.fix in FIXABLE_ISSUE_TYPES


def test_step_lookup_clamps_to_the_guide():
    assert step(1) is STEPS[0]
    assert step(0) is STEPS[0]
    assert step(99) is STEPS[-1]


def test_roles_are_explained_in_plain_words():
    for role, explanation in ROLES.items():
        assert len(explanation.split()) >= 8, role
