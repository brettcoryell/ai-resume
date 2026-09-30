-- Elementum source material identifies Brett's role as Engagement Manager.
-- A previous structured extraction used the global profile headline instead.
update ai_resume.experiences
set title = 'Engagement Manager'
where company_name = 'Elementum'
  and title = 'Chief Technology Officer';
