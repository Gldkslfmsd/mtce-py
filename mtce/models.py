from django.db import models
from django.utils.translation import ugettext as _
from django.db import transaction
import os
import shutil
# Create your models here.

from django.core.exceptions import ValidationError

from django.contrib.contenttypes.models import ContentType


from .evaluators import metric_NA, BOOTSTRAP_EVALUATORS

class ModelBase():

    def __str__(self):
        return self.name


    ######################
    # file structure

    upload_to_base = "files"
    upload_to_tmp = os.path.join("files","tmp")
    structure_base = os.path.join("files","comparisons")

    @staticmethod
    def name_to_und(name):
        return name.replace(" ", '_').replace("/","-")

    def copy_to(self, origin, new):
        dir = os.path.dirname(new)
        if not os.path.exists(dir):
            os.makedirs(dir)
        if origin == new: return
        shutil.copyfile(origin, new)

    def count_number_of_lines(self, A):
        n = 0
        with open(A,"r") as fA:
            for line in fA:
#                print(line)
                n += 1
#        print(n)
#        print()
        return n

    def correct_number_of_lines(self, A,B):
        nA, nB = self.count_number_of_lines(A), self.count_number_of_lines(B)
        if nA != nB or nA == 0:
            return False
        return True


class FileWrapper(ModelBase, models.Model):

    name = models.CharField(max_length=200)

    is_imported = models.BooleanField(default=False)
    is_corrupted = models.BooleanField(default=False)
    is_checked = models.BooleanField(default=False)

    def clear_evals(self):
        # TODO
        pass

    def update_data_import(self):
        raise NotImplementedError("override this")

    # based on this:
    # https://stackoverflow.com/questions/929029/how-do-i-access-the-child-classes-of-an-object-in-django-without-knowing-the-nam
    real_type = models.ForeignKey(ContentType, editable=False, on_delete=models.CASCADE)

    def save(self, *a, **kw):
        if self._state.adding:
            self.real_type = self._get_real_type()
        super().save(*a,**kw)
        self.cast().update_data_import()

    def _get_real_type(self):
        return ContentType.objects.get_for_model(type(self))

    def cast(self):
        return self.real_type.get_object_for_this_type(pk=self.pk)


    ############
    def browse_sentences(self, type, beg=None, end=None):
        if type == "translation":
            fn = self.translationfile()
        elif type == "source":
            fn = self.sourcefile()
        elif type == "reference":
            fn = self.referencefile()
        else:
            raise ValueError
        if not beg:
            beg = 0
        if not end:
            end = -1
        with open(fn, "r") as f:
            lines = f.readlines()
        return lines[beg:end]




class Comparison(FileWrapper):

    origsourcefile = models.FileField(
        upload_to=ModelBase.upload_to_tmp,
        help_text=_("Text file with one source sentence per line")
    )

    origreferencefile = models.FileField(
        upload_to=ModelBase.upload_to_tmp,
        help_text=_("Text file with one reference sentence per line")
    )

    description = models.TextField(max_length=5000, default="", blank=True, help_text="Optional dataset description")

    def systems_checkpoints(self):
        return ((s,c) for s in self.mtsystem_set.all() for c in s.checkpoint_set.all())



    #################
    # file structure

    def sourcefile(self):
        return os.path.join(self.base_dir(),"source.txt")

    def referencefile(self):
        return os.path.join(self.base_dir(),"reference.txt")

    def base_dir(self):
        basename = os.path.join(self.structure_base, self.name_to_und(self.name))#+"__%d" % self.id)
        return basename

    def update_file_structure(self):
        if self.is_checked: return
        self.copy_to(self.origsourcefile.name, self.sourcefile())
        self.copy_to(self.origreferencefile.name, self.referencefile())

        if not self.correct_number_of_lines(self.sourcefile(), self.referencefile()):
            self.is_corrupted = True
        self.is_checked = True
        self.save()


    def delete_file_structure(self):
        if os.path.exists(self.base_dir()):
            shutil.rmtree(self.base_dir())

    @staticmethod
    def find_by_name(name):
        return Comparison.objects.get(name=ModelBase.name_to_und(name))



    def update_data_import(self):
        src = self.sourcefile()
        ref = self.referencefile()
        di = create_or_get_DataImport(src,"source.txt",self)
        di.set_correct_time()
        di.save()
        di = create_or_get_DataImport(ref,"reference.txt",self)
        di.set_correct_time()
        di.save()

        for e in Evaluation.objects.filter(reference_dataimport=di):
            e.delete()
        for _,ch in self.systems_checkpoints():
            print("comparison: scheduling evaluation for ",ch)
            ch.schedule_evaluation()





    def list_source_reference(self, beg=None, end=None):
        return list(zip(self.browse_sentences("source", beg=beg, end=end),self.browse_sentences("reference",beg=beg,end=end)))







def create_MTSystem(name, comp):
    return MTSystem(name=ModelBase.name_to_und(name),comparison=comp)

class MTSystem(ModelBase, models.Model):
    name = models.CharField(max_length=200)

    def clean_fields(self,*a,**kw):
#        print([s.name for s in self.comparison.mtsystem_set.all()])
        if self.name in [s.name for s in self.comparison.mtsystem_set.all() if s!=self]:
            raise ValidationError('MTSystem name already used.')


    comparison = models.ForeignKey(Comparison, on_delete=models.CASCADE)

    description = models.TextField(max_length=5000, default="", blank=True, help_text="Optional MTSystem description")

    def checkpoints(self):
        return self.checkpoint_set.all()

    def base_dir(self):
        basename = os.path.join(self.comparison.base_dir(), self.name_to_und(self.name))#+"__%d" % self.id)
        return basename

    def delete_file_structure(self):
        if os.path.exists(self.base_dir()):
            shutil.rmtree(self.base_dir())

    is_imported = models.BooleanField(default=False)


    @staticmethod
    def find_by_name(name):
        return MTSystem.objects.get(name=ModelBase.name_to_und(name))








def create_Checkpoint(name,trans,sys):
    return Checkpoint(name=ModelBase.name_to_und(name),origtranslationfile=trans,mtsystem=sys)

class Checkpoint(FileWrapper):

    def clean_fields(self,*a,**kw):
        if self.name in set(s.name for s in self.mtsystem.checkpoint_set.all() if s!=self):
            raise ValidationError('Checkpoint name already used.')

    mtsystem = models.ForeignKey(MTSystem, on_delete=models.CASCADE)

    step = models.IntegerField(default=-1, help_text="MT system trainings steps of this checkpoint. Optional.")
    epoch = models.FloatField(default=-1, help_text="Number of epochs (aka iterations on training data) for this checkpoint. Optional.")
    time = models.IntegerField(default=-1, help_text="Training time in number of seconds needed to obtain this checkpoint. Optional.")


    origtranslationfile = models.FileField(
        upload_to=ModelBase.upload_to_tmp,
        help_text=_("Translation file")
    )

    def comparison(self):
        return self.mtsystem.comparison

    def base_dir(self):
        basename = os.path.join(self.mtsystem.base_dir(), self.name_to_und(self.name))#+"__%d" % self.id)
        return basename

    def translationfile(self):
        return os.path.join(self.base_dir(), "translation.txt")

    def translation(self):
        return self.translationfile()

    def reference(self):
        return self.comparison().referencefile()

    def update_file_structure(self):
        if self.is_checked: return
        self.copy_to(self.origtranslationfile.name, self.translationfile())
        if not self.correct_number_of_lines(self.translationfile(), self.mtsystem.comparison.sourcefile()):
            self.is_corrupted = True
        self.is_checked = True
        self.save()

    def delete_file_structure(self):
        if os.path.exists(self.base_dir()):
            shutil.rmtree(self.base_dir())

    def get_translation(self):
        with open(self.translationfile(),"r") as f:
            return f.read()
    def get_lines_count(self):
        return self.count_number_of_lines(self.translationfile())

    def schedule_evaluation(self):
        if not EvalJob.objects.filter(checkpoint=self).exclude(state="stopped").exists():
            with transaction.atomic():
                for metrics in EVALUATORS.keys():
                    job = EvalJob.create_new(metric=metrics,checkpoint=self)
                    job.save()
                for metric,samples,sizes in BOOTSTRAP_EVALUATORS.keys():
                    for s in range(samples):
                        job = EvalJob.create_new(metric=metric,checkpoint=self,subsample=s)
                        job.save()

    def update_data_import(self):
        tr = self.translationfile()
        di = create_or_get_DataImport(tr,"translation.txt",self)
        di.set_correct_time()
        di.save()

        self.schedule_evaluation()

    def get_metric_value(self,metric):
        e = Evaluation.objects.filter(metric=metric,checkpoint=self).first()
        if e is None:
            return metric_NA[metric]
        return e.value


















########################################################################################x
# Data imports

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

@receiver(post_save, sender=Comparison, weak=False)
@receiver(post_save, sender=Checkpoint, weak=False)
def post_save_receiver(senderclass=None, signal=None, instance=None, created=False, update_fields=None, raw=False, using='default', **kwargs):
    instance.update_file_structure()
   # print("post save receiver")
   # print(instance,created,update_fields,"raw",raw)
   # print()
    #instance.update_data_import(created,update_fields)


@receiver(pre_delete, sender=Comparison, weak=False)
@receiver(pre_delete, sender=Checkpoint, weak=False)
@receiver(pre_delete, sender=MTSystem)
def pre_delete_receiver(senderclass=None, signal=None, instance=None, created=False, update_fields=None, raw=False, using='default', **kwargs):
    instance.delete_file_structure()

##################


type_dict = { 'source.txt':1, 'reference.txt': 2, 'translation.txt':3 }

def create_DataImport(file, type, obj):
    return DataImport(path=file,type=type_dict[type],object=obj,last_change=DataImport.last_modification_time(file))

def create_or_get_DataImport(file, type, obj):
    if DataImport.objects.filter(path=file,type=type_dict[type],object=obj).exists():
        return DataImport.objects.filter(path=file,type=type_dict[type],object=obj).first()
    return create_DataImport(file, type, obj)

class DataImport(models.Model):
    last_change = models.FloatField()
    path = models.CharField(max_length=1024)
    object = models.ForeignKey(FileWrapper, on_delete=models.CASCADE)
    type = models.IntegerField()

    def set_correct_time(self):
        self.last_change = DataImport.last_modification_time(self.path)

    @staticmethod
    def needs_new_import(file):
        if DataImport.objects.filter(path=file).exists():
            return False
        return True

    @staticmethod
    def last_modification_time(file):
        return os.path.getctime(file)

    @staticmethod
    def needs_reimport(file):
        try:
            di = DataImport.objects.get(path=file)
        except DataImport.DoesNotExist:
            return True
        t = DataImport.last_modification_time(file)
        d = di.last_change
        #print(t,d)
        return t!=d

    @staticmethod
    def reimport(file, type):
        print(file)
        di = DataImport.objects.get(path=file)
        obj = di.object
        if type == "source.txt":
            obj.origsourcefile = file
        elif type == "reference.txt":
            obj.origreferencefile = file
            obj.clear_evals()
        elif type == "translation.txt":
            obj.origtranslationfile = file
            obj.clear_evals()
        else:
            raise ValueError("wrong type")
        di.last_change = DataImport.last_modification_time(file)
        di.save()
        obj.is_checked = False
        obj.save()
#
#        for e in Evaluation.objects.filter(checkpoint_dataimport=di):
#            e.delete()
#        for e in Evaluation.objects.filter(reference_dataimport=di):
#            e.delete()
#        for ej in list(EvalJob.objects.filter(checkpoint_dataimport=di))+list(EvalJob.objects.filter(reference_dataimport=di)):
#            if ej.state == "running":
#                ej.state = "stopped"
#            else:
#                ej.delete()







class EvalBase(models.Model):
    metric = models.CharField(max_length=50)
    checkpoint = models.ForeignKey(Checkpoint, on_delete=models.CASCADE)
    checkpoint_dataimport = models.ForeignKey(DataImport, on_delete=models.CASCADE, related_name="+")
    reference_dataimport = models.ForeignKey(DataImport, on_delete=models.CASCADE)
    subsample = models.IntegerField(default=-1)

    def __str__(self):
        return "%s:%s" % (self.checkpoint, self.metric)


class Evaluation(EvalBase):
    value = models.FloatField()

    def __str__(self):
        return "%s:%s=%2.2f" % (self.checkpoint, self.metric, self.value)



JOB_STATES=[("w","waiting"),("s","scheduled"),("r","running"),("st","stopped"),("f","finished"),("failed","failed")]

import random
import time
from .evaluators import EVALUATORS
from .bootstrap import get_mask



class EvalJob(EvalBase):

    state = models.CharField(default="waiting",max_length=50)
    priority = models.IntegerField(default=0)


    def __str__(self):
        return "%s:%s,state=%s" % (self.checkpoint, self.metric, self.state)


    def schedule(self):
        self.state = "scheduled"
        self.save()

    @staticmethod
    def create_new(metric,checkpoint,subsample=-1):
        cdi = DataImport.objects.get(object=checkpoint.mtsystem.comparison,type=type_dict["reference.txt"])
        chdi = DataImport.objects.get(object=checkpoint)
        return EvalJob(metric=metric,checkpoint=checkpoint,reference_dataimport=cdi,checkpoint_dataimport=chdi,subsample=subsample)

    @staticmethod
    def waiting_jobs():
        return EvalJob.objects.filter(state="waiting").all()

    def launch(self):
        self.state = "running"
        self.save()
        print("##launching job %s" % self.metric)
        if self.subsample == -1:
            mask = None
        else:
            mask = get_mask(self.checkpoint.translation(),self.subsample)
        results = EVALUATORS[self.metric].eval(self.checkpoint.translation(),self.checkpoint.reference(),mask=mask)
        if self.state == "running":
            for m,r in zip(self.metric.split(), results):
                e = Evaluation(metric=m, checkpoint=self.checkpoint, value=r,
                               checkpoint_dataimport=self.checkpoint_dataimport,
                               reference_dataimport=self.reference_dataimport,
                               subsample=self.subsample)
                e.save()
            self.state = "finished"
            self.save()
            print("##job finished",self.metric)
        else:
            print("##job was stopped")
        self.delete()

    @staticmethod
    def acquire_job_or_none():
        job = EvalJob.objects.select_for_update(nowait=True).filter(state="waiting").first()
        #print("EvalJob acquiring job!!!!",job)
        if job is not None:
            job.state = "scheduled"
            job.save()
        return job

    @staticmethod
    def acquire_pack_of_jobs_or_none(num):
        with transaction.atomic():
            jobs = []
            for i in range(num):
                j = EvalJob.acquire_job_or_none()
                if j is not None:
                    jobs.append(j)
                else:
                    break
            return jobs










