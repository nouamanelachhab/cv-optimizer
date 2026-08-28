# -*- coding: utf-8 -*-
"""Lexique de competences pour l'analyse ATS (hors-ligne).

Les mots-cles sont regroupes par categorie. Ils sont utilises pour detecter,
dans une offre d'emploi, les competences attendues, puis pour verifier leur
presence dans le CV. Couvre l'informatique, le SIRH / Paie / RH, les methodes
et les soft skills, en francais et en anglais.
"""

SKILLS = {
    "Langages": [
        "PHP", "Java", "JavaScript", "TypeScript", "Python", "C#", "C++", "C",
        "Go", "Golang", "Rust", "Kotlin", "Swift", "Ruby", "Scala", "Perl",
        "SQL", "PL/SQL", "T-SQL", "PL-SQL", "Bash", "Shell", "PowerShell",
        "HTML", "CSS", "SASS", "SCSS", "R", "MATLAB", "VBA", "COBOL", "ABAP",
        "Objective-C", "Dart", "Groovy", "Assembly", "Solidity",
    ],
    "Frameworks & Bibliotheques": [
        "Spring", "Spring Boot", "Symfony", "Laravel", "Zend", "Zend Framework",
        "CodeIgniter", "Django", "Flask", "FastAPI", "Express", "NestJS",
        "Node.js", "React", "React.js", "Angular", "Vue.js", "Vue", "Svelte",
        "Next.js", "Nuxt", "jQuery", "Bootstrap", "Tailwind", "Doctrine",
        "Hibernate", "JPA", "Quarkus", "Micronaut", ".NET", "ASP.NET",
        "Entity Framework", "Ruby on Rails", "Spark", "TensorFlow", "PyTorch",
        "Pandas", "NumPy", "Scikit-learn", "Redux", "RxJS", "GraphQL",
    ],
    "Bases de donnees": [
        "Oracle", "MySQL", "MariaDB", "PostgreSQL", "SQL Server", "SQLite",
        "MongoDB", "Redis", "Cassandra", "Elasticsearch", "DynamoDB",
        "Firebase", "Neo4j", "Snowflake", "BigQuery", "Sybase", "DB2",
        "Base de donnees", "Modelisation de donnees", "Data warehouse",
        "ETL", "SSIS", "SSRS", "Talend", "Power BI", "Tableau", "Qlik",
    ],
    "DevOps & Cloud": [
        "Docker", "Kubernetes", "Jenkins", "GitLab", "GitLab CI", "GitHub",
        "GitHub Actions", "CI/CD", "Ansible", "Terraform", "Vagrant",
        "AWS", "Azure", "GCP", "Google Cloud", "Cloud", "OpenShift",
        "Nginx", "Apache", "Tomcat", "Linux", "Unix", "Windows Server",
        "Prometheus", "Grafana", "ELK", "Kafka", "RabbitMQ", "Microservices",
        "Serverless", "Helm", "ArgoCD", "Maven", "Gradle", "npm", "Webpack",
    ],
    "Securite": [
        "Cybersécurité", "Sécurité", "PKI", "X.509", "TLS", "SSL", "TLS/SSL",
        "S/MIME", "Chiffrement", "Cryptographie", "SAST", "DAST", "Checkmarx",
        "SonarQube", "OWASP", "OWASP Top 10", "Pentest", "Test d'intrusion",
        "IAM", "SSO", "OAuth", "OAuth2", "OpenID", "JWT", "SIEM", "Firewall",
        "VPN", "Audit de securite", "RGPD", "ISO 27001", "EBIOS", "DevSecOps",
        "Vulnerabilite", "Antivirus", "Authentification", "Habilitations",
    ],
    "Outils & Methodes": [
        "Git", "SVN", "Jira", "Confluence", "Trello", "Redmine", "Bitbucket",
        "Agile", "Scrum", "Kanban", "SAFe", "Cycle en V", "Waterfall",
        "TMA", "Tierce Maintenance Applicative", "TDD", "BDD", "UML", "Merise",
        "Swagger", "OpenAPI", "Postman", "SOAP", "REST", "API REST", "API",
        "Webservices", "Web services", "Microservices", "Design pattern",
        "Tests unitaires", "Tests d'integration", "Recette", "Recette fonctionnelle",
        "Qualification", "Integration continue", "Deploiement continu",
    ],
    "SIRH / Paie / RH": [
        "SIRH", "Paie", "Gestion de la paie", "Bulletin de paie", "Bulletins de paie",
        "Declarations sociales", "DSN", "Charges sociales", "Cotisations",
        "Gestion des temps", "Suivi des temps", "Temps de travail",
        "Gestion administrative", "Absences", "Conges", "GTA",
        "Administration du personnel", "Ressources humaines", "RH",
        "Teams RH", "HR Access", "Cegid", "Sage Paie", "ADP", "Silae",
        "Workday", "SuccessFactors", "PeopleSoft", "Talentsoft",
        "Reglementation sociale", "Droit social", "Convention collective",
        "Parametrage", "Parametrage fonctionnel", "Reporting", "Reporting RH",
        "Indicateurs de performance", "KPI", "Tableau de bord",
    ],
    "Support & Maintenance": [
        "Support", "Support utilisateur", "Assistance", "Assistance utilisateur",
        "Helpdesk", "Hotline", "Support N1", "Support N2", "Support N3",
        "Incident", "Gestion des incidents", "Anomalie", "Anomalies techniques",
        "Maintenance corrective", "Maintenance preventive", "Maintenance evolutive",
        "Demande d'evolution", "Demandes d'evolution", "ITIL", "SLA",
        "Mise en production", "Run", "Exploitation", "Monitoring", "Supervision",
        "Ateliers de cadrage", "Cadrage", "Conception", "Analyse fonctionnelle",
    ],
    "Soft skills": [
        "Autonomie", "Rigueur", "Dynamique", "Proactif", "Proactivite",
        "Sens du service", "Service client", "Travail en equipe", "Esprit d'equipe",
        "Communication", "Adaptabilite", "Curiosite", "Force de proposition",
        "Organisation", "Gestion des priorites", "Resolution de problemes",
        "Relationnel", "Ecoute", "Polyvalence", "Reactivite", "Pedagogie",
    ],
    "Langues": [
        "Anglais", "Francais", "Espagnol", "Allemand", "Italien", "English",
        "Bilingue", "Courant", "Technique",
    ],
}


def all_skills():
    """Retourne la liste a plat de toutes les competences connues."""
    seen = []
    lowered = set()
    for terms in SKILLS.values():
        for t in terms:
            key = t.lower()
            if key not in lowered:
                lowered.add(key)
                seen.append(t)
    return seen


def category_of(term):
    """Retourne la categorie d'un terme (ou 'Autre')."""
    low = term.lower()
    for cat, terms in SKILLS.items():
        for t in terms:
            if t.lower() == low:
                return cat
    return "Autre"
