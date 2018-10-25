# Generated by Django 2.1.2 on 2018-10-24 14:38

from django.db import migrations, models
import django.db.models.deletion
import mtce.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Checkpoint',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('step', models.IntegerField(default=-1)),
                ('time', models.IntegerField(default=-1)),
                ('translationfile', models.FileField(help_text='Translation file', upload_to='files/translations')),
            ],
            bases=(models.Model, mtce.models.StrName),
        ),
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('sourcefile', models.FileField(help_text='Text file with one source sentence per line', upload_to='files/dataset/sources')),
                ('referencefile', models.FileField(help_text='Text file with one reference sentence per line', upload_to='files/dataset/references')),
            ],
            bases=(models.Model, mtce.models.StrName),
        ),
        migrations.CreateModel(
            name='MTSystem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True, default='', help_text='Optional MTSystem description', max_length=5000)),
                ('dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mtce.Dataset')),
            ],
            bases=(models.Model, mtce.models.StrName),
        ),
        migrations.AddField(
            model_name='checkpoint',
            name='mtsystem',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mtce.MTSystem'),
        ),
    ]
