import argparse
import os
from datetime import date
from pathlib import Path

from openreview.api.client import OpenReviewClient
from openreview.tools import get_profiles


def get_args():
    parser = argparse.ArgumentParser(description='Accepted meta-data downloader')
    parser.add_argument(
        '--email', default=os.environ.get('OPENREVIEW_EMAIL'),
        help='email address for your OpenReview profile (defaults to $OPENREVIEW_EMAIL)'
    )
    parser.add_argument(
        '--password', default=os.environ.get('OPENREVIEW_PASSWORD'),
        help='password for your OpenReview profile (defaults to $OPENREVIEW_PASSWORD)'
    )
    parser.add_argument('--venue', required=True, help='OpenReview venue ID starting with thecvf.com/ECCV/2026/Workshop/')
    parser.add_argument('--abstract', default='abstract', help='abstract field key in your submission form (JSON)')
    parser.add_argument('--archival_status', default='archival_status', help='archival status field key in your submission form (JSON)')
    parser.add_argument('--use_meta_review', action='store_true', help='use meta-review notes to find accepted papers, instead of decision notes')
    parser.add_argument('--recommendation', default='recommendation', help='recommendation field key in your meta-review form (JSON). Ignore if you run this script WITHOUT --use_meta_review')
    parser.add_argument('--decision', default='decision', help='decision field key in your decision form (JSON). Ignore if you run this script WITH --use_meta_review')
    parser.add_argument('--output', required=True, help='output tsv file path')
    args = parser.parse_args()
    if not args.email or not args.password:
        parser.error(
            'missing credentials: pass --email/--password, or set OPENREVIEW_EMAIL and '
            'OPENREVIEW_PASSWORD (e.g. in a .env file)'
        )
    return args


def extract_user_contact_info(profile, splits_name=False):
    or_id = profile.id
    name_dicts = profile.content['names']
    full_name = None
    for name_dict in name_dicts:
        preferred = name_dict.get('preferred', False)
        if full_name is not None and not preferred:
            continue

        if 'fullname' in name_dict:
            full_name = name_dict['fullname']
        else:
            full_name = name_dict['first'] + ' ' + name_dict['last']
        if splits_name:
            names = full_name.split(' ')
            first_name, last_name = names[0], names[-1]
            first_name = name_dict.get('first', first_name)
            middle_name = name_dict.get('middle')
            last_name = name_dict.get('last', last_name)
            full_name = (full_name, first_name, middle_name, last_name)
        if preferred:
            break

    assert full_name is not None or not profile.active
    email_address = profile.get_preferred_email()
    if email_address is None:
        email_address = profile.content['emailsConfirmed'][0]

    history_items = profile.content.get('history', None)
    current_year = date.today().year
    current_affiliation_list = list()
    if history_items is not None:
        for item in history_items:
            end_year = item.get('end', None)
            if end_year is None or (isinstance(end_year, str) and len(end_year) == 0) or int(end_year) >= current_year:
                institution_info = item.get('institution', dict())
                inst_name = institution_info.get('name', None)
                if inst_name is not None and len(inst_name) > 0:
                    current_affiliation_list.append(inst_name)
    return or_id, full_name, email_address, current_affiliation_list


def extract_name_and_email_address(profile_dict):
    total_num_users = len(profile_dict)
    print(f'{total_num_users} users were fetched')
    user_dict = dict()
    for key, user_profile in profile_dict.items():
        or_id, fullname, email_address, _ = extract_user_contact_info(user_profile, splits_name=False)
        user_dict[or_id] = (fullname, email_address)
    return user_dict


def extract_author_ids(submission_note):
    if 'authorids' not in submission_note.content and 'authors' in submission_note.content:
        author_items = submission_note.content['authors']['value']
        return [author_item['username'] if isinstance(author_item, dict) else author_item for author_item in author_items]
    return submission_note.content['authorids']['value']


def get_accepted_submissions_and_author_id_set(client, target_venue_group, uses_meta_review, recommendation_key):
    accepted_submission_list = list()
    target_submission_venue_id = target_venue_group.content['submission_venue_id']['value']
    author_id_set = set()
    for submission in client.get_all_notes(content={'venueid': target_submission_venue_id}, details='replies'):
        done = False
        for reply in submission.details['replies']:
            for invitation in reply['invitations']:
                if (uses_meta_review and invitation.endswith('Meta_Review')
                        and 'accept' in reply['content'][recommendation_key]['value'].lower()):
                    done = True
                elif invitation.endswith('Decision') and 'accept' in reply['content']['decision']['value'].lower():
                    done = True

                if done:
                    break
            if done:
                break
        if done:
            accepted_submission_list.append(submission)
            author_id_set.update(extract_author_ids(submission))
    return accepted_submission_list, author_id_set


def download_submissions(client, venue_id, abstract_key, archival_status_key, submissions, author_ids, output_file_path):
    profiles = get_profiles(
        client, author_ids, with_publications=False, with_preferred_emails=f'{venue_id}/-/Preferred_Emails'
    )
    profile_dict = {profile.id: profile for profile in profiles}
    username2name_and_email_address = extract_name_and_email_address(profile_dict)
    profile_dict = {p.id: p for p in profiles}
    username2profile_id = dict()
    for p in profiles:
        profile_id = p.id
        for name in p.content['names']:
            username = name.get('username')
            if username is not None:
                username2profile_id[username] = profile_id

    paper_id2first_author_username = {s.id: [x for x in extract_author_ids(s) if x.startswith('~')][0] for s in submissions}
    max_num_authors = 0
    line_list = list()
    for note in submissions:
        contact_author_id = paper_id2first_author_username[note.id]
        if contact_author_id in username2name_and_email_address.keys():
            contact_author_name, corresponding_author_email = username2name_and_email_address[contact_author_id]

        archival_status = note.content.get(archival_status_key, dict()).get('value') or ''
        text_list = [str(note.number), note.id, note.content['title']['value'], archival_status]
        author_ids = extract_author_ids(note)
        num_authors = len(author_ids)
        if num_authors > max_num_authors:
            max_num_authors = num_authors

        corresponding_author_name = note.content.get('corresponding_author_name', dict()).get('value')
        corresponding_author_email = note.content.get('corresponding_author_email', dict()).get('value')
        for idx, author_id in enumerate(author_ids):
            if author_id.startswith('~') and author_id in username2profile_id:
                profile_id = username2profile_id[author_id]
                profile = profile_dict[profile_id]
                or_id, (fullname, first_name, middle_name, last_name), email_address, inst_names = extract_user_contact_info(
                    profile, splits_name=True
                )
            else:
                fullname, first_name, middle_name, last_name, email_address, inst_names = 'N/A', 'N/A', None, 'N/A', 'N/A', ['N/A']
                if not author_id.startswith('~') and '@' not in author_id:
                    fullname = author_id

            inst_name = '; '.join(inst_names)
            if idx == 0:
                if corresponding_author_name is None:
                    corresponding_author_name = fullname
                    corresponding_author_email = email_address

                text_list.extend(
                    [
                        corresponding_author_name, corresponding_author_email,
                        note.content.get(abstract_key, dict()).get('value', '').replace('\n', '').replace('\t', ' ')
                    ]
                )

            if middle_name is not None and len(middle_name) > 0:
                first_name = f'{first_name} {middle_name}'
            text_list.extend([fullname, first_name, last_name, email_address.replace('\t', ''), inst_name.replace('\t', '')])

        line_list.append('\t'.join(text_list))

    output_file_path = os.path.expanduser(output_file_path)
    Path(output_file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file_path, 'w', encoding='utf-8') as fp:
        header = '\t'.join(
            ['Number', 'ID', 'Title', 'Archival Status', 'Contact author name', 'Contact author email', 'Abstract']
            + ['Author full name', 'Author first name', 'Author last name', 'Author email', 'Author affiliation'] * max_num_authors
        )
        fp.write(f'{header}\n')
        for line in line_list:
            fp.write(f'{line}\n')


def download_accepted_submissions(
        client, target_venue_group, abstract_key, archival_status_key, uses_meta_review, recommendation_key,
        output_file_path
):
    accepted_submissions, author_id_set = get_accepted_submissions_and_author_id_set(
        client, target_venue_group, uses_meta_review, recommendation_key
    )
    download_submissions(
        client, target_venue_group.id, abstract_key, archival_status_key, accepted_submissions,
        list(author_id_set), output_file_path
    )


def main(args):
    print(args)
    client = OpenReviewClient(
        baseurl='https://api2.openreview.net',
        username=args.email,
        password=args.password
    )
    venue_id = args.venue
    client.impersonate(group_id=venue_id)
    target_venue_group = client.get_group(venue_id)
    download_accepted_submissions(
        client, target_venue_group, args.abstract, args.archival_status, args.use_meta_review, args.recommendation,
        args.output
    )


if __name__ == '__main__':
    main(get_args())