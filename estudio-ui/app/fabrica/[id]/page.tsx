import EstudioFabrica from "@/components/EstudioFabrica";

export default async function Pagina({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <EstudioFabrica id={id} />;
}
