# Generated by Django 4.1.9 on 2023-06-01 20:50

from django.db import migrations

SQL = """
----------------------------------------------------------------------
-- Determines the (mutually exclusive) system label for a msg record
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_determine_system_label(_msg msgs_msg) RETURNS CHAR(1) STABLE AS $$
BEGIN
  IF _msg.direction = 'I' THEN
    -- incoming IVR messages aren't part of any system labels
    IF _msg.msg_type = 'V' THEN
      RETURN NULL;
    END IF;

    IF _msg.visibility = 'V' AND _msg.status = 'H' AND _msg.flow_id IS NULL THEN
      RETURN 'I';
    ELSIF _msg.visibility = 'V' AND _msg.status = 'H' AND _msg.flow_id IS NOT NULL THEN
      RETURN 'W';
    ELSIF _msg.visibility = 'A'  AND _msg.status = 'H' THEN
      RETURN 'A';
    END IF;
  ELSE
    IF _msg.VISIBILITY = 'V' THEN
      IF _msg.status = 'I' OR _msg.status = 'Q' OR _msg.status = 'E' THEN
        RETURN 'O';
      ELSIF _msg.status = 'W' OR _msg.status = 'S' OR _msg.status = 'D' THEN
        RETURN 'S';
      ELSIF _msg.status = 'F' THEN
        RETURN 'X';
      END IF;
    END IF;
  END IF;

  RETURN NULL; -- might not match any label
END;
$$ LANGUAGE plpgsql;


----------------------------------------------------------------------
-- Trigger procedure to update user and system labels on column changes
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_on_change() RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP IN ('INSERT', 'UPDATE') THEN
    -- prevent illegal message states
    IF NEW.direction = 'I' AND NEW.status NOT IN ('P', 'H') THEN
      RAISE EXCEPTION 'Incoming messages can only be PENDING or HANDLED';
    END IF;
    IF NEW.direction = 'O' AND NEW.visibility = 'A' THEN
      RAISE EXCEPTION 'Outgoing messages cannot be archived';
    END IF;
  END IF;

  -- existing message updated
  IF TG_OP = 'UPDATE' THEN
    -- restrict changes
    IF NEW.direction <> OLD.direction THEN RAISE EXCEPTION 'Cannot change direction on messages'; END IF;
    IF NEW.created_on <> OLD.created_on THEN RAISE EXCEPTION 'Cannot change created_on on messages'; END IF;
    IF NEW.msg_type <> OLD.msg_type THEN RAISE EXCEPTION 'Cannot change msg_type on messages'; END IF;

    -- is being archived or deleted (i.e. no longer included for user labels)
    IF OLD.visibility = 'V' AND NEW.visibility != 'V' THEN
      PERFORM temba_insert_message_label_counts(NEW.id, FALSE, -1);
    END IF;

    -- is being restored (i.e. now included for user labels)
    IF OLD.visibility != 'V' AND NEW.visibility = 'V' THEN
      PERFORM temba_insert_message_label_counts(NEW.id, FALSE, 1);
    END IF;

  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;


----------------------------------------------------------------------
-- Handles INSERT statements on msg table
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_on_insert() RETURNS TRIGGER AS $$
BEGIN
    -- add broadcast counts for all new broadcast values
    INSERT INTO msgs_broadcastmsgcount("broadcast_id", "count", "is_squashed")
    SELECT broadcast_id, count(*), FALSE FROM newtab WHERE broadcast_id IS NOT NULL GROUP BY broadcast_id;

    -- add system label counts for all messages which belong to a system label
    INSERT INTO msgs_systemlabelcount("org_id", "label_type", "count", "is_squashed")
    SELECT org_id, temba_msg_determine_system_label(newtab), count(*), FALSE FROM newtab
    WHERE temba_msg_determine_system_label(newtab) IS NOT NULL
    GROUP BY org_id, temba_msg_determine_system_label(newtab);

    -- add channel counts for all messages with a channel
    INSERT INTO channels_channelcount("channel_id", "count_type", "day", "count", "is_squashed")
    SELECT channel_id, temba_msg_determine_channel_count_code(newtab), created_on::date, count(*), FALSE FROM newtab
    WHERE channel_id IS NOT NULL GROUP BY channel_id, temba_msg_determine_channel_count_code(newtab), created_on::date;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;


----------------------------------------------------------------------
-- Handles UPDATE statements on msg table
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_on_update() RETURNS TRIGGER AS $$
BEGIN
    -- add negative counts for all old non-null system labels that don't match the new ones
    INSERT INTO msgs_systemlabelcount("org_id", "label_type", "count", "is_squashed")
    SELECT o.org_id, temba_msg_determine_system_label(o), -count(*), FALSE FROM oldtab o
    INNER JOIN newtab n ON n.id = o.id
    WHERE temba_msg_determine_system_label(o) IS DISTINCT FROM temba_msg_determine_system_label(n) AND temba_msg_determine_system_label(o) IS NOT NULL
    GROUP BY o.org_id, temba_msg_determine_system_label(o);

    -- add counts for all new system labels that don't match the old ones
    INSERT INTO msgs_systemlabelcount("org_id", "label_type", "count", "is_squashed")
    SELECT n.org_id, temba_msg_determine_system_label(n), count(*), FALSE FROM newtab n
    INNER JOIN oldtab o ON o.id = n.id
    WHERE temba_msg_determine_system_label(o) IS DISTINCT FROM temba_msg_determine_system_label(n) AND temba_msg_determine_system_label(n) IS NOT NULL
    GROUP BY n.org_id, temba_msg_determine_system_label(n);

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;


----------------------------------------------------------------------
-- Handles DELETE statements on msg table
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_on_delete() RETURNS TRIGGER AS $$
BEGIN
    -- add negative system label counts for all messages that belonged to a system label
    INSERT INTO msgs_systemlabelcount("org_id", "label_type", "count", "is_squashed")
    SELECT org_id, temba_msg_determine_system_label(oldtab), -count(*), FALSE FROM oldtab
    WHERE temba_msg_determine_system_label(oldtab) IS NOT NULL
    GROUP BY org_id, temba_msg_determine_system_label(oldtab);

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER temba_msg_on_update
AFTER UPDATE ON msgs_msg REFERENCING OLD TABLE AS oldtab NEW TABLE AS newtab
FOR EACH STATEMENT EXECUTE PROCEDURE temba_msg_on_update();


CREATE TRIGGER temba_msg_on_delete
AFTER DELETE ON msgs_msg REFERENCING OLD TABLE AS oldtab
FOR EACH STATEMENT EXECUTE PROCEDURE temba_msg_on_delete();


CREATE TRIGGER temba_msg_on_change
AFTER INSERT OR UPDATE ON msgs_msg
FOR EACH ROW EXECUTE PROCEDURE temba_msg_on_change();

DROP TRIGGER temba_msg_on_change_trg ON msgs_msg;
"""


class Migration(migrations.Migration):
    dependencies = [("msgs", "0239_update_db_triggers")]

    operations = [migrations.RunSQL(SQL)]