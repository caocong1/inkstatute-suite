from hermes_contract_layer.hook import handle as _handle


def handle(event_type, context):
    return _handle(event_type, context)
