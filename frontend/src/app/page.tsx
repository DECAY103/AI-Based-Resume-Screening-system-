export default function Home() {
  return (
    <main className="project-intro">
      <section className="project-intro__content" aria-labelledby="project-title">
        <p className="eyebrow">Software Engineering Project</p>
        <h1 id="project-title">AI-based Resume Screening</h1>
        <p className="project-intro__summary">
          A streamlined workspace for uploading resumes, evaluating candidate
          profiles, and reviewing ranked results.
        </p>

        <div className="project-intro__rule" aria-hidden="true" />

        <section className="contributors" aria-labelledby="contributors-heading">
          <h2 id="contributors-heading">Contributors</h2>
          <ul>
            <li>Harsha B <span>— 241IT031</span></li>
            <li>Harshith R <span>— 241IT032</span></li>
            <li>Rohith Marthula <span>— 241IT044</span></li>
          </ul>
        </section>

        <section className="course-instructor" aria-labelledby="instructor-heading">
          <h2 id="instructor-heading">Course Instructor</h2>
          <p>Prof. Jaidhar C D</p>
        </section>

        <a className="primary project-intro__cta" href="/auth/login">
          Open screening portal
        </a>
      </section>
      <p className="project-intro__footer">© 2026 AI-based Resume Screening. All rights reserved.</p>
    </main>
  );
}
