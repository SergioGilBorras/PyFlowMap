async def export_data(opener, selector, writer):
    async with opener() as source:
        async with writer() as target:
            rows = await source.rows()
            if not rows:
                return 0
            selected = [row for row in rows if selector(row)]
            await target.write(selected)
            return len(selected)
