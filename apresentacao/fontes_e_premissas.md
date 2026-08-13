# Fontes e premissas — Receita Certa

## Fontes primárias

- Código atual dos repositórios:
  - `/home/rafaelamorim/repo/api_prontocardio`
  - `/home/rafaelamorim/repo/prj_glosas`
  - `/home/rafaelamorim/repo/prj_web_nfs`
- Estudo interno:
  - `/home/rafaelamorim/repo/querys_oracle/FATURAMENTO/apresentacao_custo_beneficio_zero_glosa.pdf`
- Contexto operacional e estratégico fornecido pelo solicitante.

Os READMEs foram tratados como apoio. Para as funcionalidades, prevaleceram telas, rotas, modelos, regras de negócio, testes e histórico Git, pois o solicitante informou que a documentação está desatualizada.

## Números do comparativo ZeroGlosa

Período: fevereiro de 2025 a junho de 2026, com dados atualizados em 23/06/2026.

- Receita avaliada: R$ 87,43 milhões.
- Receita coberta: R$ 13,44 milhões (15,4%).
- Receita fora do escopo: R$ 74,00 milhões (84,6%).
- Contas cobertas: 17.893 (12,9%).
- Contas fora do escopo: 120.663.
- Custo bruto acumulado: R$ 104,4 mil.
- Limitação registrada no estudo: não havia histórico integrado de recursos e recuperações atribuível ao fornecedor.

## Cálculos derivados

- Custo médio mensal: R$ 104.400 ÷ 17 meses = R$ 6.141.
- Custo anualizado no mesmo ritmo: aproximadamente R$ 73.694.
- Custo por conta coberta: R$ 104.400 ÷ 17.893 = R$ 5,83.
- Break-even sobre a receita coberta: R$ 104.400 ÷ R$ 13,44 milhões = 0,78%.
- Percentual da base fora do escopo necessário para equivaler ao custo bruto: R$ 104.400 ÷ R$ 74,00 milhões = 0,141%.
- Sensibilidades sobre R$ 74,00 milhões:
  - 0,1% = R$ 74 mil;
  - 0,5% = R$ 370 mil;
  - 1,0% = R$ 740 mil.

## Cuidados de interpretação

- Os cenários econômicos não são benefícios realizados.
- A apresentação não afirma cobertura integral do Receita Certa. O código permite configuração multiconvênio; a cobertura efetiva depende de dados, implantação e adoção.
- O custo interno total de propriedade ainda precisa ser levantado: desenvolvimento, infraestrutura, sustentação, segurança, contingência e horas operacionais.
- A comparação com a ZeroGlosa deve considerar recuperação atribuível, cobertura, dependência operacional e TCO — não apenas preço.
- A contagem de 292 cenários de teste corresponde a funções de teste catalogadas no código em 29/07/2026, não a um relatório de execução.
- O nome usado é “Receita Certa”, porque é o nome exibido na interface atual. Se o nome institucional definitivo for “Receita Pronta”, os textos devem ser substituídos antes da apresentação.
