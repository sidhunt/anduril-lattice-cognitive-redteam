import pytest
import numpy as np
from lattice_cognitive.engine.maslow import MotivationProfile, MaslowLevel
from lattice_cognitive.engine.markov_chain import AdversarialMarkovChain, STATE_TO_IDX


def test_transition_matrix_row_stochastic():
    profile = MotivationProfile()
    chain = AdversarialMarkovChain(profile)
    matrix = chain.transition_matrix

    # Check 5x5 dimensions
    assert matrix.shape == (5, 5)

    # Every row must sum to 1.0 (stochastic matrix property)
    for i in range(5):
        row_sum = np.sum(matrix[i])
        assert pytest.approx(row_sum, 0.0001) == 1.0


def test_observation_update_modifies_probabilities():
    profile = MotivationProfile()
    chain = AdversarialMarkovChain(profile)
    chain.current_state = MaslowLevel.SECURITY
    curr_idx = STATE_TO_IDX[MaslowLevel.SECURITY]

    initial_survival_prob = chain.transition_matrix[curr_idx][STATE_TO_IDX[MaslowLevel.SURVIVAL]]

    # Trigger radar lock
    chain.update_from_lattice_observation(
        radar_lock=True,
        intercept_dispatched=False,
        operator_hesitation_ms=1500.0,
        decoy_survived=True,
    )

    updated_survival_prob = chain.transition_matrix[curr_idx][STATE_TO_IDX[MaslowLevel.SURVIVAL]]
    assert updated_survival_prob > initial_survival_prob
    assert pytest.approx(np.sum(chain.transition_matrix[curr_idx]), 0.0001) == 1.0


def test_markov_step_and_directives():
    profile = MotivationProfile()
    chain = AdversarialMarkovChain(profile)
    next_state, telemetry = chain.step()

    assert isinstance(next_state, MaslowLevel)
    assert "from_state" in telemetry
    assert "to_state" in telemetry
    assert telemetry["to_state"] == next_state.value

    directive = chain.get_tactical_directive()
    assert "altitude_offset_m" in directive
    assert "speed_multiplier" in directive
    assert "tactic" in directive
