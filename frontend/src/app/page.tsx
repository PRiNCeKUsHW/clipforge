import { ProjectList } from "@/components/project-list";
import { RequireAuth } from "@/components/require-auth";
import { SubmitForm } from "@/components/submit-form";

export default function HomePage() {
  return (
    <RequireAuth>
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-14">
        <section className="hero-glow flex flex-col gap-7">
          <div className="flex flex-col gap-4 pt-4">
            <h1 className="max-w-[16ch] text-[2.6rem] leading-[1.02] font-extrabold sm:text-6xl">
              One long video in, a week of Shorts out.
            </h1>
            <p className="max-w-[58ch] text-base leading-relaxed text-muted-foreground sm:text-lg">
              Paste a YouTube link or drop in a file. ClipForge finds the funniest, sharpest moments, frames them
              for vertical, and scores each clip so you know what to post first.
            </p>
          </div>
          <SubmitForm />
        </section>
        <section className="flex flex-col gap-4">
          <h2 className="text-2xl font-bold">Your projects</h2>
          <ProjectList />
        </section>
      </div>
    </RequireAuth>
  );
}
