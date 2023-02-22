-- Generated by collect_sql on 2023-02-22 18:37 UTC

CREATE INDEX IF NOT EXISTS campaigns_eventfire_fired_not_null_idx on campaigns_eventfire(fired) WHERE fired IS NOT NULL;

CREATE UNIQUE INDEX campaigns_eventfire_unfired_unique
ON campaigns_eventfire (event_id, contact_id, (fired IS NULL))
WHERE fired IS NULL;

-- indexes for fast fetching of android channels by last seen
CREATE INDEX IF NOT EXISTS channels_channel_android_last_seen_active
ON channels_channel(last_seen ASC NULLS LAST) WHERE channel_type = 'A' and is_active = True;

-- index for fast fetching of unsquashed rows
CREATE INDEX channels_channelcount_unsquashed
ON channels_channelcount(channel_id, count_type, day) WHERE NOT is_squashed;

CREATE INDEX channels_channellog_channel_created_on
ON channels_channellog(channel_id, created_on desc);

CREATE INDEX contacts_contact_modified_on ON contacts_contact(modified_on);

CREATE INDEX contacts_contact_org_modified_id_active
ON contacts_contact (org_id, modified_on DESC, id DESC)
WHERE is_active = true;

CREATE INDEX contacts_contact_org_modified_id_inactive
ON contacts_contact (org_id, modified_on DESC, id DESC)
WHERE is_active = false;

-- index for fast fetching of unsquashed rows
CREATE INDEX contacts_contactgroupcount_unsquashed
ON contacts_contactgroupcount(group_id) WHERE NOT is_squashed;

CREATE INDEX contacts_contacturn_org_scheme_display ON contacts_contacturn (org_id, scheme, display)WHERE display IS NOT NULL;

CREATE INDEX contacts_contacturn_path ON contacts_contacturn (org_id, UPPER(path), contact_id);

-- indexes for fast fetching of unsquashed rows
CREATE INDEX flows_flowcategorycount_unsquashed
ON flows_flowcategorycount(flow_id, node_uuid, result_key, result_name, category_name) WHERE NOT is_squashed;

CREATE INDEX flows_flownodecount_unsquashed
ON flows_flownodecount(flow_id, node_uuid) WHERE NOT is_squashed;

CREATE INDEX flows_flowpathcount_unsquashed ON flows_flowpathcount(flow_id, from_uuid, to_uuid, period) WHERE NOT is_squashed;

CREATE INDEX flows_flowrun_flow_modified_id ON flows_flowrun (flow_id, modified_on DESC, id DESC);

CREATE INDEX flows_flowrun_flow_modified_id_where_responded ON flows_flowrun (flow_id, modified_on DESC, id DESC) WHERE responded = TRUE;

CREATE INDEX flows_flowrun_org_modified_id ON flows_flowrun (org_id, modified_on DESC, id DESC);

CREATE INDEX flows_flowrun_org_modified_id_where_responded ON flows_flowrun (org_id, modified_on DESC, id DESC) WHERE responded = TRUE;

-- for removing ended sessions
CREATE INDEX flows_flowsession_ended_on_not_null
ON flows_flowsession(ended_on ASC)
WHERE ended_on IS NOT NULL;

CREATE INDEX flows_flowsession_timeout
ON flows_flowsession(timeout_on) WHERE timeout_on IS NOT NULL AND status = 'W';

-- for finding the waiting session for a contact
CREATE INDEX flows_flowsession_waiting
ON flows_flowsession(contact_id)
WHERE status = 'W';

-- index for fast fetching of unsquashed rows
CREATE INDEX flows_flowstartcount_unsquashed
ON flows_flowstartcount(start_id) WHERE NOT is_squashed;

CREATE INDEX locations_adminboundary_name on locations_adminboundary(upper("name"));

CREATE INDEX locations_boundaryalias_name on locations_boundaryalias(upper("name"));

CREATE INDEX IF NOT EXISTS msgs_broadcast_sending_idx ON msgs_broadcast(org_id, created_on) WHERE status = 'Q';

CREATE INDEX msgs_msg_channel_external_id_not_null
ON msgs_msg (channel_id, external_id)
WHERE external_id IS NOT NULL;

CREATE INDEX msgs_msg_contact_id_created_on ON msgs_msg (contact_id, created_on desc);

CREATE INDEX msgs_msg_org_created_id_where_outbound_visible_failed
ON msgs_msg(org_id, created_on DESC, id DESC)
WHERE direction = 'O' AND visibility = 'V' AND status = 'F';

CREATE INDEX msgs_msg_org_created_id_where_outbound_visible_outbox
ON msgs_msg(org_id, created_on DESC, id DESC)
WHERE direction = 'O' AND visibility = 'V' AND status IN ('P', 'Q');

CREATE INDEX IF NOT EXISTS msgs_msg_org_id_created_on_id_idx on msgs_msg(org_id, created_on, id);

CREATE INDEX msgs_msg_org_modified_id_where_inbound
ON msgs_msg (org_id, modified_on DESC, id DESC)
WHERE direction = 'I';

CREATE INDEX msgs_msg_visibility_type_created_id_where_inbound
ON msgs_msg(org_id, visibility, msg_type, created_on DESC, id DESC)
WHERE direction = 'I';

-- index for fast fetching of unsquashed rows
CREATE INDEX msgs_systemlabel_unsquashed
ON msgs_systemlabelcount(org_id, label_type) WHERE NOT is_squashed;

