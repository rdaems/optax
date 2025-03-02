# Copyright 2019 DeepMind Technologies Limited. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Gradient transformations used to enforce specific constraints."""

from typing import Any, NamedTuple

import jax
import jax.numpy as jnp

from optax._src import base

# pylint:disable=no-value-for-parameter


NonNegativeParamsState = base.EmptyState


def keep_params_nonnegative() -> base.GradientTransformation:
  """Modifies the updates to keep parameters non-negative, i.e. >= 0.

  This transformation ensures that parameters after the update will be
  larger than or equal to zero.
  In a chain of transformations, this should be the last one.

  WARNING: the transformation expects input params to be non-negative.
  When params is negative the transformed update will move them to 0.

  Returns:
    An (init_fn, update_fn) tuple.
  """

  def init_fn(_):
    return NonNegativeParamsState()

  def update_fn(updates, state, params):
    if params is None:
      raise ValueError(base.NO_PARAMS_MSG)

    updates = jax.tree_multimap(
        lambda p, u: jnp.where((p + u) < 0., -p, u), params, updates)
    return updates, state

  return base.GradientTransformation(init_fn, update_fn)


class ZeroNansState(NamedTuple):
  """Contains a tree.

  The entry `found_nan` has the same tree structure as that of the parameters.
  Each leaf is a single boolean which contains True iff a NaN was detected in
  the corresponding parameter array at the last call to `update`.
  """
  found_nan: Any


def zero_nans() -> base.GradientTransformation:
  """A transformation which replaces NaNs with 0.

  Zeroing values in gradients is guaranteed to produce a direction of
  non-increasing loss.

  The state of the transformation has the same tree structure as that of the
  parameters. Each leaf is a single boolean which contains True iff a NaN was
  detected in the corresponding parameter array at the last call to `update`.
  This state is not used by the transformation internally, but lets users be
  aware when NaNs have been zeroed out.

  Returns:
    A `GradientTransformation`.
  """

  def init_fn(params):
    return ZeroNansState(
        jax.tree_map(lambda p: jnp.array(False, dtype=jnp.bool_), params))

  def update_fn(updates, opt_state, params=None):
    del params
    opt_state = ZeroNansState(
        jax.tree_map(lambda p: jnp.any(jnp.isnan(p)), updates))
    updates = jax.tree_map(
        lambda p: jnp.where(jnp.isnan(p), jnp.zeros_like(p), p), updates)
    return updates, opt_state

  return base.GradientTransformation(init=init_fn, update=update_fn)
