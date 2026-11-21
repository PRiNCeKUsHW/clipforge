import { ProjectList } from "@/components/project-list";
import { RequireAuth } from "@/components/require-auth";
import { SubmitForm } from "@/components/submit-form";

export default function HomePage() {
  return (
    <RequireAuth>
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-10">
        <section className="flex flex-col gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Long video in. Viral shorts out.</h1>
            <p className="mt-2 text-muted-foreground">
              Paste a YouTube link or upload a file. ClipForge transcribes it locally, asks Gemini for the strongest
              moments, and cuts scored clips you can download.
            </p>
          </div>
          <SubmitForm />
        </section>
        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold">Your projects</h2>
          <ProjectList />
        </section>
      </div>
    </RequireAuth>
  );
}
