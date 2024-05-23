from typing import Dict, List

import pandas as pd
from pydantic import BaseModel


class Parameter(BaseModel):
    key: str
    value: str


ParametersInput = List[Parameter]


class Input(BaseModel):
    pass


class InferenceInput(Input):
    @classmethod
    def label_order(cls):
        return sorted(cls.__fields__.keys())

    @classmethod
    def to_dataframe(cls, input_: List, exclude: List = None):
        # TODO types here should not be repr()
        columns = cls.label_order()
        for col in exclude:
            columns.remove(col)
        return pd.DataFrame(data=[i.dict() for i in input_], columns=columns)

    @classmethod
    def preprocess(cls, input_: Dict):
        return input_

    @classmethod
    def to_list(cls, input_: List, field_name: str):
        # TODO types here should not be repr()
        return [getattr(i, field_name) for i in input_]

# Basic inference types


class TextInput(InferenceInput):
    text: str
