# Copyright 2018-2021 Streamlit Inc.
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

"""Form unit tests."""

import streamlit as st
from streamlit.errors import StreamlitAPIException
from tests import testutil

NO_FORM_ID = ""


class FormAssociationTest(testutil.DeltaGeneratorTestCase):
    """Tests for every flavor of form/deltagenerator association."""

    def _get_last_checkbox_form_id(self) -> str:
        """Return the form ID for the last checkbox delta that was enqueued."""
        last_delta = self.get_delta_from_queue()
        self.assertIsNotNone(last_delta)
        self.assertEqual("new_element", last_delta.WhichOneof("type"))
        self.assertEqual("checkbox", last_delta.new_element.WhichOneof("type"))
        return last_delta.new_element.checkbox.form_id

    def test_no_form(self):
        """By default, an element doesn't belong to a form."""
        st.checkbox("widget")
        self.assertEqual(NO_FORM_ID, self._get_last_checkbox_form_id())

    def test_implicit_form_parent(self):
        """Within a `with form` statement, any `st.foo` element becomes
        part of that form."""
        with st.beta_form("form"):
            st.checkbox("widget")
        self.assertEqual("form", self._get_last_checkbox_form_id())

        # The sidebar, and any other DG parent created outside
        # the form, does not create children inside the form.
        with st.beta_form("form2"):
            st.sidebar.checkbox("widget2")
        self.assertEqual(NO_FORM_ID, self._get_last_checkbox_form_id())

    def test_deep_implicit_form_parent(self):
        """Within a `with form` statement, any `st.foo` element becomes
        part of that form, regardless of how deeply nested the element is."""
        with st.beta_form("form"):
            cols1 = st.beta_columns(2)
            with cols1[0]:
                with st.beta_container():
                    st.checkbox("widget")
        self.assertEqual("form", self._get_last_checkbox_form_id())

        # The sidebar, and any other DG parent created outside
        # the form, does not create children inside the form.
        with st.beta_form("form2"):
            cols1 = st.beta_columns(2)
            with cols1[0]:
                with st.beta_container():
                    st.sidebar.checkbox("widget2")
        self.assertEqual(NO_FORM_ID, self._get_last_checkbox_form_id())

    def test_parent_created_inside_form(self):
        """If a parent DG is created inside a form, any children of
        that parent belong to the form."""
        with st.beta_form("form"):
            with st.beta_container():
                # Create a (deeply nested) column inside the form
                form_col = st.beta_columns(2)[0]

                # Attach children to the column in various ways.
                # They'll all belong to the form.
                with form_col:
                    st.checkbox("widget1")
                    self.assertEqual("form", self._get_last_checkbox_form_id())

                    form_col.checkbox("widget2")
                    self.assertEqual("form", self._get_last_checkbox_form_id())

        form_col.checkbox("widget3")
        self.assertEqual("form", self._get_last_checkbox_form_id())

    def test_parent_created_outside_form(self):
        """If our parent was created outside a form, any children of
        that parent have no form, regardless of where they're created."""
        no_form_col = st.beta_columns(2)[0]
        no_form_col.checkbox("widget1")
        self.assertEqual(NO_FORM_ID, self._get_last_checkbox_form_id())

        with st.beta_form("form"):
            no_form_col.checkbox("widget2")
            self.assertEqual(NO_FORM_ID, self._get_last_checkbox_form_id())

            with no_form_col:
                st.checkbox("widget3")
                self.assertEqual(NO_FORM_ID, self._get_last_checkbox_form_id())


class FormMarshallingTest(testutil.DeltaGeneratorTestCase):
    """Test ability to marshall form protos."""

    def test_multiple_forms_same_key(self):
        """Multiple forms with the same key are not allowed."""

        with self.assertRaises(StreamlitAPIException) as ctx:
            st.beta_form(key="foo")
            st.beta_form(key="foo")

        self.assertIn(
            "There are multiple identical forms with `key='foo'`", str(ctx.exception)
        )

    def test_multiple_forms_same_labels_different_keys(self):
        """Multiple forms with different keys are allowed."""

        try:
            st.beta_form(key="foo")
            st.beta_form(key="bar")

        except Exception:
            self.fail("Forms with same labels and different keys failed to create.")

    def test_form_in_form(self):
        """Test that forms cannot be nested in other forms."""

        with self.assertRaises(StreamlitAPIException) as ctx:
            with st.beta_form("foo"):
                with st.beta_form("bar"):
                    pass

        self.assertEqual(str(ctx.exception), "Forms cannot be nested in other forms.")

    def test_button_in_form(self):
        """Test that buttons are not allowed in forms."""

        with self.assertRaises(StreamlitAPIException) as ctx:
            with st.beta_form("foo"):
                st.button("foo")

        self.assertEqual(str(ctx.exception), "Button can't be used in a form.")

    def test_form_block_id(self):
        """Test that a form creates a block element with a correct id."""

        # Calling `with` will invoke `__exit__` on `DeltaGenerator`
        with st.beta_form(key="foo"):
            pass

        # Check that we create a form block element
        self.assertEqual(len(self.get_all_deltas_from_queue()), 1)
        form_proto = self.get_delta_from_queue(0).add_block
        self.assertIn("foo", form_proto.form_id)

    def test_form_block_data(self):
        """Test that a form creates a block element with correct data."""

        form_data = st.beta_form(key="bar")._form_data
        self.assertIn("bar", form_data.form_id)

    # (HK) TODOs:
    # - columns inside a form
    # - a form inside of columns
    # - file uploader (after Tim's refactor)
