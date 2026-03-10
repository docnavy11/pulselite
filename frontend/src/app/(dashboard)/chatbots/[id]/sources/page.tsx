"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function SourcesPage() {
  const params = useParams();
  const router = useRouter();

  useEffect(() => {
    router.replace(`/chatbots/${String(params.id)}`);
  }, [params.id, router]);

  return null;
}
