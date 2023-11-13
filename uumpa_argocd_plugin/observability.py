import os
import json
import contextlib


def init():
    if os.environ.get('ENABLE_OTLP'):
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry import trace

        resource = Resource(attributes={
            SERVICE_NAME: "uumpa-argocd-plugin"
        })
        provider = TracerProvider(resource=resource)
        endpoint = os.environ.get('OTLP_ENDPOINT') or 'http://localhost:4317'
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
        trace.set_tracer_provider(provider)


def _get_current_span(span=None):
    from opentelemetry import trace
    return span if span else trace.get_current_span()


@contextlib.contextmanager
def start_as_current_span(name, name_suffix=None, *args, attributes=None, **kwargs):
    if os.environ.get('ENABLE_OTLP'):
        from opentelemetry import trace
        if callable(name):
            name = f'{name.__module__}.{name.__name__}'
        if name_suffix:
            name = f'{name}{name_suffix}'
        with trace.get_tracer(__name__).start_as_current_span(name, *args, **kwargs) as span:
            if attributes:
                set_attributes(**attributes)
            yield span
    else:
        yield None


def set_attribute(key, value):
    if os.environ.get('ENABLE_OTLP'):
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        _get_current_span().set_attribute(key, value)


def set_attributes(**attributes):
    if os.environ.get('ENABLE_OTLP'):
        for key, value in attributes.items():
            set_attribute(key, value)


def add_event(name, attributes=None, span=None, **kwargs):
    if os.environ.get('ENABLE_OTLP'):
        span = _get_current_span(span)
        if attributes:
            kwargs['attributes'] = {}
            for k, v in attributes.items():
                if isinstance(v, (dict, list)) or v is None:
                    v = json.dumps(v)
                kwargs['attributes'][k] = v
        span.add_event(name, **kwargs)
