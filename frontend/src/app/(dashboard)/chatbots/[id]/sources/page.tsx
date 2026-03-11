import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";

export default function SourcesPage() {
  const { id } = useParams() as { id: string };
  const navigate = useNavigate();

  useEffect(() => {
    navigate(`/chatbots/${id}`, { replace: true });
  }, [id, navigate]);

  return null;
}
