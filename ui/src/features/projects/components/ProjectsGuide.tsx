import { Link } from "react-router";

import { API_KEYS_ROUTE, LOGS_ROUTE } from "../../../constants/ui";

/** Client → project → environment, explained with examples. */
export function HowItIsOrganized() {
  return (
    <ol className="hierarchy" aria-label="How Spanport organizes your work">
      <li className="hierarchy-step">
        <span className="hierarchy-name">Client</span>
        <span className="text-secondary text-sm">
          Who the software is for. Your own company works too.
        </span>
        <span className="hierarchy-example">e.g. GenHRX</span>
      </li>
      <li className="hierarchy-step">
        <span className="hierarchy-name">Project</span>
        <span className="text-secondary text-sm">One of that client&apos;s apps or services.</span>
        <span className="hierarchy-example">e.g. Backend API</span>
      </li>
      <li className="hierarchy-step">
        <span className="hierarchy-name">Environment</span>
        <span className="text-secondary text-sm">
          Where it runs. Each one has its own keys and logs.
        </span>
        <span className="hierarchy-example">e.g. production, qa</span>
      </li>
    </ol>
  );
}

/** Shown until the first project exists: the three steps to the first logs. */
export function GettingStarted() {
  return (
    <section className="panel" aria-label="Get your first logs in">
      <h2 className="panel-title">Get your first logs in</h2>
      <ol className="steps">
        <li className="step step-current">
          <span className="step-number">1</span>
          <span>
            <strong>Add a project</strong>
            <span className="text-secondary text-sm"> with the form above.</span>
          </span>
        </li>
        <li className="step">
          <span className="step-number">2</span>
          <span>
            <strong>Create a data key</strong>
            <span className="text-secondary text-sm">
              {" "}
              for it on <Link to={API_KEYS_ROUTE}>API keys</Link>. It is shown once.
            </span>
          </span>
        </li>
        <li className="step">
          <span className="step-number">3</span>
          <span>
            <strong>Send logs</strong>
            <span className="text-secondary text-sm">
              {" "}
              with <code className="code-inline">pip install spanport</code> or{" "}
              <code className="code-inline">npm install spanport</code>, then watch them arrive on{" "}
              <Link to={LOGS_ROUTE}>Logs</Link>.
            </span>
          </span>
        </li>
      </ol>
    </section>
  );
}
