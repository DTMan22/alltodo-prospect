-- alltodo-prospect : schéma isolé (projet Supabase SÉPARÉ de alltodo)
-- Exécuter dans le SQL editor du nouveau projet.

create table if not exists prospects (
  id uuid primary key default gen_random_uuid(),
  uid_che text unique,                 -- CHE-xxx.xxx.xxx
  raison_sociale text not null,
  forme_juridique text,
  canton text,                         -- VD, GE...
  commune text,
  adresse text,
  noga_code text,
  noga_label text,
  but_statutaire text,
  date_inscription date,               -- création FOSC
  source text default 'zefix',         -- zefix | fosc | localch | csv_legacy
  telephone text,
  email text,
  site_web text,
  dirigeant_nom text,
  canton text,                        -- code 2 lettres (VD, GE...) via table communes
  uid_che text,                       -- CHE-xxx.xxx.xxx (CompanyUID LINDAS)
  description text,                   -- but statutaire (fr si dispo)
  score_icp int default 0,             -- 0-100, calculé côté ingestion
  statut text default 'nouveau',       -- nouveau | contacte | interesse | inscrit | rejete
  created_at timestamptz default now()
);
create index if not exists idx_prospects_canton on prospects(canton);
create index if not exists idx_prospects_noga on prospects(noga_code);
create index if not exists idx_prospects_statut on prospects(statut);
create index if not exists idx_prospects_date on prospects(date_inscription desc);

create table if not exists prospect_events (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid references prospects(id) on delete cascade,
  type text not null,                  -- creation | capital | dirigeant | adresse | succursale
  details jsonb default '{}',
  seen_at date default current_date,
  created_at timestamptz default now()
);

-- Blocklist légale (nLPD/LCD) : ne JAMAIS recontacter
create table if not exists optout (
  email text primary key,
  reason text,
  created_at timestamptz default now()
);

-- Traçabilité des imports manuels (CSV legacy local.ch)
create table if not exists imports (
  id uuid primary key default gen_random_uuid(),
  filename text,
  rows int,
  created_at timestamptz default now()
);
