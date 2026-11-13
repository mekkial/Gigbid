import math

from evals.runners.judge_calibration import binom_two_sided, cohen_kappa, weighted_kappa


def test_kappa_known_values():
    assert cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    assert abs(cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0])) < 1e-9                   # chance-level agreement
    # textbook example: 20 agree-yes, 15 agree-no, 5 + 10 disagreements -> kappa = 0.4 (Wikipedia worked example is 0.4 for 45/..)
    a = [1] * 25 + [0] * 25; b = [1] * 20 + [0] * 5 + [1] * 10 + [0] * 15
    assert math.isclose(cohen_kappa(a, b), 0.4, abs_tol=1e-9)


def test_weighted_kappa_penalises_far_disagreement_more():
    near = weighted_kappa([1, 2, 3, 4, 5, 3], [2, 2, 3, 4, 4, 3]); far = weighted_kappa([1, 2, 3, 4, 5, 3], [5, 2, 3, 4, 1, 3])
    assert near > far and weighted_kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0


def test_binomial_p_value():
    assert binom_two_sided(10, 10) < 0.005 and binom_two_sided(5, 10) == 1.0
