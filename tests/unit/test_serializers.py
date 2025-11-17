from cachine.serializers import JSONSerializer, PickleSerializer


def test_json_serializer_roundtrip() -> None:
    s = JSONSerializer()
    data = {"a": 1, "b": [2, 3]}
    assert s.loads(s.dumps(data)) == data


def test_pickle_serializer_roundtrip() -> None:
    s = PickleSerializer()
    data = {"a": 1, "b": [2, 3]}
    assert s.loads(s.dumps(data)) == data
