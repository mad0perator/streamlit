# Copyright 2018-2020 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import textwrap
from typing import cast, Optional, NamedTuple

import streamlit
from streamlit.elements.utils import _get_widget_id
from streamlit.errors import StreamlitAPIException
from streamlit.proto.RootContainer_pb2 import RootContainer
from streamlit.proto import Block_pb2, Button_pb2
from streamlit.report_thread import get_report_ctx


class FormData(NamedTuple):
    """Form data stored on a DeltaGenerator."""

    # The form's unique ID.
    form_id: str
    # The label for the submit button that's automatically created for a form.
    submit_button_label: str
    # The optional key for the submit button.
    submit_button_key: Optional[str]


def _current_form(
    this_dg: "streamlit.delta_generator.DeltaGenerator",
) -> Optional[FormData]:
    """Find the FormData for the given DeltaGenerator.

    Forms are blocks, and can have other blocks nested inside them.
    To find the current form, we walk up the dg_stack until we find
    a DeltaGenerator that has FormData.
    """
    # (HK) TODO: Discuss this solution with Tim
    if this_dg._root_container == RootContainer.SIDEBAR:
        # We're being invoked via an `st.sidebar.foo` pattern - ignore the
        # current `with` dg.
        return this_dg._form_data

    ctx = get_report_ctx()
    if ctx is None or len(ctx.dg_stack) == 0:
        return this_dg._form_data

    # We're being invoked via an `st.foo` pattern
    for dg in reversed(ctx.dg_stack):
        if dg._form_data is not None:
            return dg._form_data

    return this_dg._form_data


def _create_form_id(submit_label: str, key: Optional[str]) -> str:
    """Create an ID for a form.

    A form's ID is equal to its Submit button's widget ID. To make it,
    we fake up our Submit button - which need not have been created yet.
    We know that this ID will be unique across all forms, because widget IDs
    are unique across widgets, and this widget ID will be registered when the
    form's Submit button is created.
    """
    # To generate an ID for the form, we fake up our Submit button -
    # which is not yet created - and use its ID. (We know that this ID
    # will be unique among all forms, because widget IDs are among all
    # widgets, and this widget ID will be registered when the form's
    # Submit button is created.)
    button_proto = Button_pb2.Button()
    button_proto.label = submit_label
    button_proto.default = False
    button_proto.is_form_submitter = True
    return _get_widget_id("button", button_proto, user_key=key)


def current_form_id(dg: "streamlit.delta_generator.DeltaGenerator") -> str:
    """Return the form_id for the current form, or the empty string if we're
    not inside an `st.form` block.

    (We return the empty string, instead of None, because this value is
    assigned to protobuf message fields, and None is not valid.)
    """
    form_data = _current_form(dg)
    if form_data is None:
        return ""
    return form_data.form_id


def is_in_form(dg: "streamlit.delta_generator.DeltaGenerator") -> bool:
    """True if the DeltaGenerator is inside an st.form block."""
    return current_form_id(dg) != ""


def _build_duplicate_form_message(user_key: Optional[str] = None) -> str:
    if user_key is not None:
        message = textwrap.dedent(
            f"""
            There are multiple identical forms with `key='{user_key}'`.

            To fix this, please make sure that the `key` argument is unique for
            each `st.beta_form` you create.
            """
        )
    else:
        message = textwrap.dedent(
            """
            There are multiple identical forms with the same generated key.

            When a form is created, it's assigned an internal key based on
            its structure. Multiple forms with an identical structure will
            result in the same internal key, which causes this error.

            To fix this error, please pass a unique `key` argument to
            `st.beta_form`.
            """
        )

    return message.strip("\n")


class FormMixin:
    def beta_form(self, submit_label="Submit", key=None):
        """TODO

        Parameters
        ----------
        submit_label
        key

        Returns
        -------

        """

        if is_in_form(self.dg):
            raise StreamlitAPIException("Forms cannot be nested in other forms.")

        form_id = _create_form_id(submit_label, key)
        ctx = get_report_ctx()
        if ctx is not None:
            added_form_id = ctx.form_ids_this_run.add(form_id)
            if not added_form_id:
                raise StreamlitAPIException(_build_duplicate_form_message(key))

        block_proto = Block_pb2.Block()
        block_proto.form_id = form_id
        block_dg = self.dg._block(block_proto)

        # Attach the form's button info to the newly-created block's
        # DeltaGenerator. The block will create its submit button when it
        # exits.
        block_dg._form_data = FormData(form_id, submit_label, key)
        return block_dg

    @property
    def dg(self) -> "streamlit.delta_generator.DeltaGenerator":
        """Get our DeltaGenerator."""
        return cast("streamlit.delta_generator.DeltaGenerator", self)
