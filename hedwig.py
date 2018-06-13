docstr = """
Hedwig
Usage:
    hedwig.py (-h | --help)
    hedwig.py (-q | -b) (-a | -r) <config_file>

Options:
-h --help        Show this message and exit
-q --query       Use the WOS api to get new publication data (not functional)
-b --bibtex      Get new publication data from bibtex file (path in config file)
-a --api         Use VIVO update api to upload data immediately
-r --rdf         Produce rdf files with new data
"""

from docopt import docopt
import os
import os.path
import datetime
import yaml

from vivo_utils import queries
from vivo_utils.connections.vivo_connect import Connection
from vivo_utils import vivo_log
from vivo_utils.triple_handler import TripleHandler
from vivo_utils.update_log import UpdateLog
from vivo_utils.connections.wos_connect import WOSnnection
from vivo_utils.handlers.wos_handler import WHandler

# import wos
# import daily_prophet

# TODO Add query method
# TODO Use daily_prophet for update e-mails

CONFIG_PATH = '<config_file>'
_query = '--query'
_bibtex = '--bibtex'
_api = '--api'
_rdf = '--rdf'

def get_config(config_path):
    try:
        with open(config_path, 'r') as config_file:
            config = yaml.load(config_file.read())
    except Exception as e:
        print("Error: Check config file")
        print(e)
        exit()
    return config

def make_folders(top_folder, sub_folders=None):
    if not os.path.isdir(top_folder):
        os.mkdir(top_folder)

    if sub_folders:
        sub_top_folder = os.path.join(top_folder, sub_folders[0])
        top_folder = make_folders(sub_top_folder, sub_folders[1:])

    return top_folder

def check_filter(abbrev_filter, name_filter, name):
    cleanfig = get_config(abbrev_filter)
    abbrev_table = cleanfig.get('abbrev_table')
    name += " " #Add trailing space
    name = name.replace('\\', '')
    for abbrev in abbrev_table:
        if (abbrev) in name:
            name = name.replace(abbrev, abbrev_table[abbrev])
    name = name[:-1] #Remove final space

    namefig = get_config(name_filter)
    try:
        if name.upper() in namefig.keys():
            name = namefig.get(name.upper())
    except AttributeError as e:
        name = name

    return name

def process(connection, publication, added_authors, tripler, ulog, db_name, filter_folder):
    abbrev_filter = os.path.join(filter_folder, 'general_filter.yaml')
    publisher_n = None
    if publication.publisher:
        p_filter = os.path.join(filter_folder, 'publisher_filter.yaml')
        publication.publisher = check_filter(abbrev_filter, p_filter, publication.publisher)
        publisher_matches = vivo_log.lookup(db_name, 'publishers', publication.publisher, 'name')
        if len(publisher_matches) == 0:
            publisher_matches = vivo_log.lookup(db_name, 'publishers', publication.publisher, 'name', True)
        if len(publisher_matches) == 1:
            publisher_n = publisher_matches[0][0]
        else:
            publisher_params = queries.make_publisher.get_params(connection)
            publisher_params['Publisher'].name = publication.publisher
            tripler.update(queries.make_publisher, **publisher_params)

            publisher_n = publisher_params['Publisher'].n_number
            ulog.add_to_log('publishers', publication.publisher, (connection.vivo_url + publisher_n))
            if len(publisher_matches) > 1:
                pbl_n_list = [publisher_n]
                for pbl_match in publisher_matches:
                    pbl_n_list.append(pbl_match[0])
                ulog.track_ambiguities(publication.publisher, pbl_n_list)

    journal_n = None
    if publication.journal:
        j_filter = os.path.join(filter_folder, 'journal_filter.yaml')
        publication.journal = check_filter(abbrev_filter, j_filter, publication.journal)
        journal_matches = vivo_log.lookup(db_name, 'journals', publication.journal, 'name')
        if len(journal_matches) == 0:
            journal_matches = vivo_log.lookup(db_name, 'journals', publication.journal, 'name', True)
            if len(journal_matches) == 0:
                journal_matches = vivo_log.lookup(db_name, 'journals', publication.issn, 'issn')
        if len(journal_matches) == 1:
            journal_n = journal_matches[0][0]
        else:
            journal_params = queries.make_journal.get_params(connection)
            journal_params['Journal'].name = publication.journal
            journal_params['Journal'].issn = publication.issn
            journal_params['Publisher'].n_number = publisher_n
            tripler.update(queries.make_journal, **journal_params)

            journal_n = journal_params['Journal'].n_number
            ulog.add_to_log('journals', publication.journal, (connection.vivo_url + journal_n))
            if len(journal_matches) > 1:
                jrn_n_list = [journal_n]
                for jrn_match in journal_matches:
                    jrn_n_list.append(jrn_match[0])
                ulog.track_ambiguities(publication.journal, jrn_n_list)

    pub_n = add_pub(connection, publication, journal_n, tripler, ulog, db_name)            

    if publication.authors:
        author_ns = []
        for author in publication.authors:
            if pub_n:
                author_n = add_authors(connection, publication, author, added_authors, tripler, ulog, db_name)
                author_ns.append((author_n, author))
            else:
                ulog.add_author_to_skips(publication.wosid, author)

    if pub_n:
        add_authors_to_pub(connection, pub_n, publication.wosid, author_ns, tripler, ulog)
        print("Pub added")

def add_pub(connection, publication, journal_n, tripler, ulog, db_name):
    pub_type = None
    query_type = None
    if publication.type == 'Article' or publication.type == 'Article; Early Access' or publication.type == 'Article; Proceedings Paper':
        pub_type = 'academic_article'
        query_type = getattr(queries, 'make_academic_article')
    elif publication.type == 'Letter':
        pub_type = 'letter'
        query_type = getattr(queries, 'make_letter')
    elif publication.type == 'Editorial Material':
        pub_type = 'editorial'
        query_type = getattr(queries, 'make_editorial_article')
    elif publication.type == 'Meeting Abstract':
        pub_type = 'abstract'
        query_type = getattr(queries, 'make_abstract')
    else:
        query_type = 'pass'

    publication_matches = vivo_log.lookup(db_name, 'publications', publication.title, 'title')
    if len(publication_matches) == 0:
        publication_matches = vivo_log.lookup(db_name, 'publications', publication.doi, 'doi')
    if len(publication_matches) == 1:
        pub_n = publication_matches[0][0]
    else:
        pub_params = queries.make_academic_article.get_params(connection)
        pub_params['Journal'].n_number = journal_n
        pub_params['Article'].name = publication.title
        pub_params['Article'].volume = publication.volume
        pub_params['Article'].issue = publication.issue
        pub_params['Article'].publication_year = publication.year
        pub_params['Article'].doi = publication.doi
        pub_params['Article'].pmid = publication.pmid
        pub_params['Article'].start_page = publication.start_page
        pub_params['Article'].end_page = publication.end_page
        pub_params['Article'].number = publication.number

        if query_type=='pass':
            ulog.track_skips(publication.wosid, publication.type, **pub_params)
            pub_n = None
        else:
            tripler.update(query_type, **pub_params)
            pub_n = pub_params['Article'].n_number
            ulog.add_to_log('articles', publication.title, (connection.vivo_url + pub_n))
            ulog.add_citation(publication, (connection.vivo_url + pub_n))

        if len(publication_matches) > 1:
            pub_n_list = []
            for pub_match in publication_matches:
                pub_n_list.append(pub_match[0])
            if pub_n:
                pub_n_list.append(pub_n)
            ulog.track_ambiguities(publication.title, pub_n_list)
    return pub_n

def add_authors(connection, publication, author, added_authors, tripler, ulog, db_name):
    first = middle = last = ""
    try:
        last, rest = author.split(', ')
        try:
            first, middle = rest.split(" ", 1)
        except ValueError as e:
            first = rest
    except ValueError as e:
        last = author
    matches = vivo_log.lookup(db_name, 'authors', author, 'display')
    if author in added_authors.keys():
        matches.append([author_n])

    if len(matches) == 0:
        matches = vivo_log.lookup(db_name, 'authors', author, 'display', True)
    if len(matches) == 1:
        author_n = matches[0][0]
    else:
        params = queries.make_person.get_params(connection)
        params['Author'].name = author
        params['Author'].last = last
        if first:
            params['Author'].first = first
        if middle:
            params['Author'].middle = middle
        tripler.update(queries.make_person, **params)

        author_n = params['Author'].n_number
        ulog.add_to_log('authors', author, (connection.vivo_url + author_n))
        added_authors[author] = author_n 
        if len(matches) > 1:
            auth_n_list = [author_n]
            for match in matches:
                auth_n_list.append(match[0])
            ulog.track_ambiguities(author, auth_n_list)
    return author_n

def add_authors_to_pub(connection, pub_n, wosid, author_ns, tripler, ulog):
    for author_n, author_name in author_ns:
        params = queries.add_author_to_pub.get_params(connection)
        params['Article'].n_number = pub_n
        params['Author'].n_number = author_n
        
        added = queries.check_author_on_pub.run(connection, **params)
        if not added:
            tripler.update(queries.add_author_to_pub, **params)

def main(args):
    if args[_query]:
        print("The query method does not work currently. Download a bibtex and use that method.")
        exit()
    config = get_config(args[CONFIG_PATH])

    email = config.get('email')
    password = config.get ('password')
    update_endpoint = config.get('update_endpoint')
    query_endpoint = config.get('query_endpoint')
    vivo_url = config.get('upload_url')
    wos_login = config.get('wos_credentials')
    filter_folder = config.get('filter_folder')

    db_name = '/tmp/vivo_temp_storage.db'

    connection = Connection(vivo_url, email, password, update_endpoint, query_endpoint)
    vivo_log.update_db(connection, db_name)
    whandler = WHandler(wos_login, False)
    now = datetime.datetime.now()

    if args[_bibtex]:
        input_file = config.get('input_file')
        csv_data = whandler.bib2csv(input_file)
        publications = whandler.parse_csv(csv_data)
    elif args[_query]:
        query = 'AD=(University Florida OR Univ Florida OR UFL OR UF)'
        begin = now - datetime.timedelta(days=3)
        start = begin.strftime("%Y-%m-%d")
        finish = now - datetime.timedelta(days=2)
        end = finish.strftime("%Y-%m-%d")
        results = whandler.get_data(query, start, end)
        publications = whandler.parse_api()

    timestamp = now.strftime("%Y_%m_%d")
    full_path = make_folders(config.get('folder_for_logs'), [now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")])

    disam_file = os.path.join(full_path, (timestamp + '_wos_disambiguation.json'))
    output_file = os.path.join(full_path, (timestamp + '_wos_output_file.txt'))
    upload_file = os.path.join(full_path, (timestamp + '_wos_upload_log.txt'))
    skips_file = os.path.join(full_path, (timestamp + '_wos_skips_.json'))
    citations_file = os.path.join(full_path, (timestamp + '_wos_citations_.txt'))
    
    tripler = TripleHandler(args[_api], connection, output_file)
    ulog = UpdateLog()

    added_authors = {}
    for publication in publications:
        process(connection, publication, added_authors, tripler, ulog, db_name, filter_folder)

    upload_file_made = ulog.create_file(upload_file)
    citation_file_made = ulog.create_citation_file(citations_file)
    ulog.write_skips(skips_file)
    ulog.write_disam_file(disam_file)

    if args[_rdf]:
        rdf_file = timestamp + '_upload.rdf'
        rdf_filepath = os.path.join(full_path, rdf_file)
        tripler.print_rdf(rdf_filepath)

    os.remove(db_name)

if __name__ == '__main__':
    args = docopt(docstr)
    main(args)