import json
from glob import glob

import pytest
from django.core.management.base import CommandError
from django.test import override_settings
from django.urls import reverse
from lxml import etree

from pretalx.agenda.tasks import export_schedule_html
from pretalx.common.tasks import regenerate_css
from pretalx.event.models import Event


@pytest.mark.django_db
def test_schedule_frab_xml_export(
    slot, client, django_assert_num_queries, schedule_schema
):
    with django_assert_num_queries(25):
        response = client.get(
            reverse(
                f'agenda:export.schedule.xml',
                kwargs={'event': slot.submission.event.slug},
            ),
            follow=True,
        )
    assert response.status_code == 200, str(response.content.decode())
    assert 'ETag' in response

    content = response.content.decode()
    assert slot.submission.title in content
    assert slot.submission.urls.public.full() in content

    parser = etree.XMLParser(schema=schedule_schema)
    etree.fromstring(
        response.content, parser
    )  # Will raise if the schedule does not match the schema
    with django_assert_num_queries(15):
        response = client.get(
            reverse(
                f'agenda:export.schedule.xml',
                kwargs={'event': slot.submission.event.slug},
            ),
            HTTP_IF_NONE_MATCH=response['ETag'],
            follow=True,
        )
    assert response.status_code == 304


@pytest.mark.django_db
def test_schedule_frab_xml_export_control_char(
    slot, client, django_assert_num_queries, schedule_schema
):
    slot.submission.description = "control char: \a"
    slot.submission.save()

    with django_assert_num_queries(24):
        response = client.get(
            reverse(
                f'agenda:export.schedule.xml',
                kwargs={'event': slot.submission.event.slug},
            ),
            follow=True,
        )

    parser = etree.XMLParser()
    etree.fromstring(response.content, parser)


@pytest.mark.django_db
def test_schedule_frab_json_export(
    slot,
    answered_choice_question,
    personal_answer,
    client,
    django_assert_num_queries,
    orga_user,
    schedule_schema,
):
    with django_assert_num_queries(26):
        regular_response = client.get(
            reverse(
                f'agenda:export.schedule.json',
                kwargs={'event': slot.submission.event.slug},
            ),
            follow=True,
        )
    client.force_login(orga_user)
    with django_assert_num_queries(23):
        orga_response = client.get(
            reverse(
                f'agenda:export.schedule.json',
                kwargs={'event': slot.submission.event.slug},
            ),
            follow=True,
        )
    assert regular_response.status_code == 200
    assert orga_response.status_code == 200

    regular_content = regular_response.content.decode()
    orga_content = orga_response.content.decode()

    assert slot.submission.title in regular_content
    assert slot.submission.title in orga_content
    assert personal_answer.answer in orga_content
    assert personal_answer.answer not in regular_content

    regular_content = json.loads(regular_content)
    orga_content = json.loads(orga_content)
    assert regular_content['schedule']
    assert orga_content['schedule']

    assert regular_content != orga_content


@pytest.mark.django_db
def test_schedule_frab_xcal_export(
    slot, client, django_assert_num_queries, schedule_schema
):
    with django_assert_num_queries(20):
        response = client.get(
            reverse(
                f'agenda:export.schedule.xcal',
                kwargs={'event': slot.submission.event.slug},
            ),
            follow=True,
        )
    assert response.status_code == 200

    content = response.content.decode()
    assert slot.submission.title in content


@pytest.mark.django_db
def test_schedule_ical_export(slot, client, django_assert_num_queries, schedule_schema):
    with django_assert_num_queries(22):
        response = client.get(
            reverse(
                f'agenda:export.schedule.ics',
                kwargs={'event': slot.submission.event.slug},
            ),
            follow=True,
        )
    assert response.status_code == 200

    content = response.content.decode()
    assert slot.submission.title in content


@pytest.mark.django_db
def test_schedule_single_ical_export(
    slot, client, django_assert_num_queries, schedule_schema
):
    with django_assert_num_queries(23):
        response = client.get(slot.submission.urls.ical, follow=True)
    assert response.status_code == 200

    content = response.content.decode()
    assert slot.submission.title in content


@pytest.mark.django_db
@pytest.mark.parametrize(
    'exporter',
    ('schedule.xml', 'schedule.json', 'schedule.xcal', 'schedule.ics', 'feed'),
)
def test_schedule_export_nonpublic(
    exporter, slot, client, django_assert_num_queries, schedule_schema
):
    slot.submission.event.is_public = False
    slot.submission.event.save()
    exporter = 'feed' if exporter == 'feed' else f'export.{exporter}'

    with django_assert_num_queries(14):
        response = client.get(
            reverse(f'agenda:{exporter}', kwargs={'event': slot.submission.event.slug}),
            follow=True,
        )
    assert response.status_code == 404


@pytest.mark.django_db
def test_schedule_speaker_ical_export(
    slot, other_slot, client, django_assert_num_queries
):
    speaker = slot.submission.speakers.all()[0]
    profile = speaker.profiles.get(event=slot.event)
    with django_assert_num_queries(32):
        response = client.get(profile.urls.talks_ical, follow=True)
    assert response.status_code == 200

    content = response.content.decode()
    assert slot.submission.title in content
    assert other_slot.submission.title not in content


@pytest.mark.django_db
def test_feed_view(slot, client, django_assert_num_queries, schedule_schema, schedule):
    with django_assert_num_queries(19):
        response = client.get(slot.submission.event.urls.feed)
    assert response.status_code == 200
    assert schedule.version in response.content.decode()


@pytest.mark.django_db
def test_html_export_event_required():
    from django.core.management import call_command

    with pytest.raises(CommandError) as excinfo:
        call_command('export_schedule_html')

    assert 'the following arguments are required: event' in str(excinfo)


@pytest.mark.django_db
def test_html_export_event_unknown(event):
    from django.core.management import call_command

    with pytest.raises(CommandError) as excinfo:
        call_command('export_schedule_html', 'foobar222')
    assert 'Could not find event with slug "foobar222"' in str(excinfo)
    export_schedule_html(event_id=22222)
    export_schedule_html(event_id=event.pk)


@pytest.mark.django_db
def test_html_export_release(mocker, event):
    mocker.patch('django.core.management.call_command')

    event.settings.export_html_on_schedule_release = True
    event.wip_schedule.freeze(name="ohaio means hello")

    from django.core.management import call_command

    call_command.assert_called_with('export_schedule_html', event.slug, '--zip')


@pytest.mark.django_db
def test_html_export_release_disabled(mocker, event):
    mocker.patch('django.core.management.call_command')

    event.settings.export_html_on_schedule_release = False
    event.wip_schedule.freeze(name="ohaio means hello")

    from django.core.management import call_command

    call_command.assert_not_called()


@pytest.mark.django_db
def test_html_export_language(event, slot):
    from django.core.management import call_command
    from django.conf import settings
    import os.path

    event.locale = 'de'
    event.locale_array = 'de,en'
    event.save()
    with override_settings(COMPRESS_ENABLED=True, COMPRESS_OFFLINE=True):
        call_command('rebuild')
        call_command('export_schedule_html', event.slug)

    schedule_html = open(
        os.path.join(settings.HTMLEXPORT_ROOT, 'test', 'test/schedule/index.html')
    ).read()
    assert 'Kontakt' in schedule_html
    assert 'locale/set' not in schedule_html  # bug #494


@pytest.mark.django_db
def test_schedule_export_schedule_html_task(mocker, event, slot):
    mocker.patch('django.core.management.call_command')

    from pretalx.agenda.tasks import export_schedule_html

    export_schedule_html.apply_async(kwargs={'event_id': event.id})

    from django.core.management import call_command

    call_command.assert_called_with('export_schedule_html', event.slug, '--zip')


@pytest.mark.django_db
def test_schedule_export_schedule_html_task_nozip(mocker, event, slot):
    mocker.patch('django.core.management.call_command')

    from pretalx.agenda.tasks import export_schedule_html

    export_schedule_html.apply_async(kwargs={'event_id': event.id, 'make_zip': False})

    from django.core.management import call_command

    call_command.assert_called_with('export_schedule_html', event.slug)


@pytest.mark.django_db
def test_schedule_orga_trigger_export(
    mocker, orga_client, django_assert_num_queries, event
):
    from pretalx.agenda.tasks import export_schedule_html

    mocker.patch('pretalx.agenda.tasks.export_schedule_html.apply_async')

    with django_assert_num_queries(34):
        response = orga_client.post(
            event.orga_urls.schedule_export_trigger, follow=True
        )
    assert response.status_code == 200
    export_schedule_html.apply_async.assert_called_once_with(
        kwargs={'event_id': event.id}
    )


@pytest.mark.django_db
def test_schedule_orga_download_export(
    mocker, orga_client, django_assert_num_queries, event, slot
):
    from pretalx.agenda.tasks import export_schedule_html

    export_schedule_html.apply_async(kwargs={'event_id': event.id, 'make_zip': True})
    with django_assert_num_queries(9):
        response = orga_client.get(
            event.orga_urls.schedule_export_download, follow=True
        )
    assert len(b"".join(response.streaming_content)) > 1_000_000  # 1MB


@pytest.mark.django_db
def test_html_export_full(event, other_event, slot, canceled_talk):
    from django.core.management import call_command
    from django.conf import settings
    import os.path

    event.primary_color = '#111111'
    event.save()
    other_event.primary_color = '#222222'
    other_event.save()

    with override_settings(COMPRESS_ENABLED=True, COMPRESS_OFFLINE=True):
        call_command('rebuild')
        regenerate_css(event.pk)
        regenerate_css(other_event.pk)
        event = Event.objects.get(slug=event.slug)
        assert event.settings.agenda_css_file
        call_command('export_schedule_html', event.slug, '--zip')

    paths = [
        'static/common/img/logo.svg',
        f'media/test/{event.settings.agenda_css_file.split("/")[-1]}',
        'test/schedule/index.html',
        'test/schedule/export/schedule.json',
        'test/schedule/export/schedule.xcal',
        'test/schedule/export/schedule.xml',
        'test/schedule/export/schedule.ics',
        *[
            f'test/speaker/{speaker.code}/index.html'
            for speaker in slot.submission.speakers.all()
        ],
        f'test/talk/{slot.submission.code}/index.html',
        f'test/talk/{slot.submission.code}.ics',
    ]

    for path in paths:
        full_path = os.path.join(settings.HTMLEXPORT_ROOT, 'test', path)
        assert os.path.exists(full_path)

    for path in glob(os.path.join(settings.HTMLEXPORT_ROOT, 'test/media/*')):
        assert event.slug in path
        assert other_event.slug not in path

    full_path = os.path.join(settings.HTMLEXPORT_ROOT, 'test.zip')
    assert os.path.exists(full_path)

    # views and templates are the same for export and online viewing, so a naive test is enough here
    talk_html = open(
        os.path.join(
            settings.HTMLEXPORT_ROOT,
            'test',
            f'test/talk/{slot.submission.code}/index.html',
        )
    ).read()
    assert talk_html.count(slot.submission.title) >= 2

    speaker = slot.submission.speakers.all()[0]
    speaker_html = open(
        os.path.join(
            settings.HTMLEXPORT_ROOT, 'test', f'test/speaker/{speaker.code}/index.html'
        )
    ).read()
    assert speaker.name in speaker_html

    schedule_html = open(
        os.path.join(settings.HTMLEXPORT_ROOT, 'test', f'test/schedule/index.html')
    ).read()
    assert 'Contact us' in schedule_html  # locale
    assert canceled_talk.submission.title not in schedule_html

    schedule_json = json.load(
        open(
            os.path.join(
                settings.HTMLEXPORT_ROOT, f'test/test/schedule/export/schedule.json'
            )
        )
    )
    assert schedule_json['schedule']['conference']['title'] == event.name

    schedule_ics = open(
        os.path.join(
            settings.HTMLEXPORT_ROOT, f'test/test/schedule/export/schedule.ics'
        )
    ).read()
    assert slot.submission.code in schedule_ics
    assert canceled_talk.submission.code not in schedule_ics

    schedule_xcal = open(
        os.path.join(
            settings.HTMLEXPORT_ROOT, f'test/test/schedule/export/schedule.xcal'
        )
    ).read()
    assert event.slug in schedule_xcal
    assert speaker.name in schedule_xcal

    schedule_xml = open(
        os.path.join(
            settings.HTMLEXPORT_ROOT, f'test/test/schedule/export/schedule.xml'
        )
    ).read()
    assert slot.submission.title in schedule_xml
    assert canceled_talk.submission.frab_slug not in schedule_xml
    assert str(canceled_talk.submission.uuid) not in schedule_xml

    talk_ics = open(
        os.path.join(
            settings.HTMLEXPORT_ROOT, f'test/test/talk/{slot.submission.code}.ics'
        )
    ).read()
    assert slot.submission.title in talk_ics


@pytest.mark.django_db
def test_speaker_csv_export(slot, orga_client, django_assert_num_queries):
    with django_assert_num_queries(17):
        response = orga_client.get(
            reverse(
                f'agenda:export',
                kwargs={'event': slot.submission.event.slug, 'name': 'speakers.csv'},
            ),
            follow=True,
        )
    assert response.status_code == 200, str(response.content.decode())
    assert slot.submission.speakers.first().name in response.content.decode()
