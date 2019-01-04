from django.shortcuts import render, get_object_or_404

# Create your views here.

from django.http import HttpResponse
from .models import Comparison, Checkpoint, MTSystem
from .evaluators import METRICS
from .charts import *
from .sentence_listing import get_all_sentences

def get_comparisons():
    return Comparison.objects.all() #order_by('name') \
       # .annotate(documents=Count('document')) \
       # .annotate(total_sentences=Count('document__sentence'))
    # tasks_table = TaskTable(tasks)

def index(request):
    """
    The initial dashboard view with a list of tasks
    """
    comparisons = get_comparisons()
    return render(
        request,
        'mtce/index.html',
        {'comparisons': comparisons,
         'active': 'index',
         },
    )

def corpus_metrics(request, comparison_id, system=None):

    comp = get_object_or_404(Comparison, pk=comparison_id)

    metrics = METRICS
    systems_checkpoints = comp.systems_checkpoints()
    if system is not None:
        systems_checkpoints = [(s,ch) for s,ch in systems_checkpoints if s == system]

    systems_checkpoints_metricvalues = [ (s,ch,[ round(ch.get_metric_value(m),2) for m in metrics]) for s,ch in systems_checkpoints ]

    pass_args = {
                   'active':"corpus_metrics",  # for menu
                   'comparison': comp,
                   'systems_checkpoints_metricvalues': systems_checkpoints_metricvalues,
                   'metrics':metrics,
                   'metric_bar_charts': [ MetricBarChart(metric,[(a,b,c[i]) for a,b,c in systems_checkpoints_metricvalues]) \
                                                         for i,metric in enumerate(metrics) ],
                   'system': system,
                   }
    return render(request,
                  'mtce/corpus_metrics.html',
                   pass_args ,
                  )

def system_index(request, system_id):
    system = get_object_or_404(MTSystem, pk=system_id)
    return corpus_metrics(request, system.comparison.id, system)

def sentences(request, comparison_id, system=None):

    comp = get_object_or_404(Comparison, pk=comparison_id)

    sentences = get_all_sentences(comp,system)[:10]
    pass_args = {
                   'active':"sentences",  # for top menu
                   'comparison': comp,
                   'system': system,
                   'sentences': sentences,
                   'first_sentences': sentences[0],
                   'metrics': sentences[0][-1].metrics,
                   }
    return render(request,
                  'mtce/sentences.html',
                   pass_args,
                  )

def system_sentences(request, system_id):
    system = get_object_or_404(MTSystem, pk=system_id)
    return sentences(request, system.comparison.id, system)


