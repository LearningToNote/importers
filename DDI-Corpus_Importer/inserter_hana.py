# this assumes a schema db called LTN_DEVELOP is created
# use db_setup/schema.sql

import json
import math

import pyhdb
import pyhdb.exceptions
from pyhdb.protocol.lobs import NClob

CHUNK_SIZE = 1000
TASK_NAME = 'Biomedical Domain (Drug-Drug-Interactions)'

with open("../secrets.json") as f:
    secrets = json.load(f)

details = secrets.get('database')
connection = pyhdb.connect(
    host=details.get('host'),
    port=details.get('port'),
    user=details.get('username'),
    password=details.get('password')
)

cursor = connection.cursor()


def insert_many(statement, values):
    if len(values) > 0:
        number_of_chunks = int(math.ceil(len(values)/float(CHUNK_SIZE)))

        try:
            for i in range(number_of_chunks):
                cursor.executemany(
                    statement,
                    values[i*CHUNK_SIZE:i*CHUNK_SIZE+CHUNK_SIZE])

        except pyhdb.exceptions.DatabaseError as e:
            print e


def store_user(id, name, token, description, image):
    cursor.execute("INSERT INTO LTN_DEVELOP.USERS VALUES(?,?,?,?,?)", (id, name, token, description, image))
    connection.commit()


def create_task(username):
    task = 1
    try:
        sql_to_prepare = 'CALL LTN_DEVELOP.add_task (?, ?, ?, ?, ?)'
        params = {
            'TASK_NAME': TASK_NAME,
            'TABLE_NAME': 'BIO_TEXTS',
            'ER_ANALYSIS_CONFIG': 'LTN::bio_text_entity_recognition',
            'NEW_AUTHOR': username,
            'TASK_ID': None
        }
        psid = cursor.prepare(sql_to_prepare)
        ps = cursor.get_prepared_statement(psid)
        cursor.execute_prepared(ps, [params])
        task = cursor.fetchone()[0]
    except Exception, e:
        print 'Warning: ', e
    return task


def get_task_id():
    try:
        cursor.execute("SELECT id FROM LTN_DEVELOP.TASKS WHERE name = ?", (TASK_NAME, ))
        return cursor.fetchone()[0]
    except:
        return None


def store(documents, user_documents, entities, pairs, offsets, task):
    for document in documents:
        try:
            sql_to_prepare = 'CALL LTN_DEVELOP.add_document (?, ?, ?)'
            params = {
                'DOCUMENT_ID': document[0],
                'DOCUMENT_TEXT': NClob(document[1].replace("'", "''")),
                'TASK': task
            }
            psid = cursor.prepare(sql_to_prepare)
            ps = cursor.get_prepared_statement(psid)
            cursor.execute_prepared(ps, [params])
        except Exception, e:
            print 'Error: ', e
    insert_many("INSERT INTO LTN_DEVELOP.USER_DOCUMENTS VALUES (?,?,?,?,?,?)", user_documents)
    insert_many("INSERT INTO LTN_DEVELOP.ENTITIES VALUES (?,?,?,?,?)", entities)
    insert_many("INSERT INTO LTN_DEVELOP.PAIRS VALUES (?,?,?,?,?,?)", pairs)
    insert_many("INSERT INTO LTN_DEVELOP.OFFSETS VALUES (?,?,?,?)", offsets)
    connection.commit()


def store_pos_tags():
    cursor.execute("DELETE FROM POS_TAGS;")
    cursor.execute("INSERT INTO POS_TAGS(POS) SELECT DISTINCT TA_TYPE FROM LTN_DEVELOP.$TA_INDEX_BIO_TEXTS;")
    connection.commit()


def insert_stop_words(stopwords):
    insert_many("INSERT INTO LTN_DEVELOP.STOPWORDS VALUES (?)", stopwords)
    connection.commit()


def insert_task_types(template, relation, task, label):
    type_id = None
    cursor.execute("SELECT ID FROM LTN_DEVELOP.TYPES WHERE CODE = ?", (template.base_type,))
    base_type = cursor.fetchone()
    if base_type:
        type_id = base_type[0]
    cursor.execute("INSERT INTO LTN_DEVELOP.TASK_TYPES(ID, LABEL, TASK_ID, TYPE_ID, RELATION) VALUES (?, ?, ?, ?, ?)",
                   (template.id, label, task, type_id, relation))
    connection.commit()
